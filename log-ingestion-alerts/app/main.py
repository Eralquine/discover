"""Orchestrator: wires the connectors to normalization, storage, rules and alerting.

Runs three concurrent pieces:
  - a Fortinet syslog listener (asyncio, its own thread)
  - a Microsoft 365 audit-log poller (its own thread, fixed interval)
  - a single-threaded worker that drains everything they produce into the DB
    and evaluates rules, so all writes go through one session at a time.

This keeps each connector simple (they just hand raw records to a queue) and
keeps rule evaluation/alerting single-threaded, which matters because the
threshold rules and cooldown checks read-then-write the same tables.
"""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import signal
import threading
import time
from dataclasses import dataclass
from typing import Any

from app.alerting import dispatch_alert
from app.config import settings
from app.connectors import m365
from app.connectors.fortinet_syslog import parse_kv, run_tcp_server, run_udp_server
from app.db import SessionLocal, init_db, store_event, store_raw_event
from app.normalize import normalize_fortinet, normalize_m365
from app.rules import evaluate_event

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("soc.main")


@dataclass
class RawItem:
    source: str  # "m365" | "fortinet"
    raw_text: str
    parsed: dict[str, Any]


_ingest_queue: "queue.Queue[RawItem]" = queue.Queue(maxsize=10_000)
_stop_event = threading.Event()


# --------------------------------------------------------------------------
# Producers
# --------------------------------------------------------------------------

def run_m365_poller() -> None:
    if not (settings.m365_tenant_id and settings.m365_client_id and settings.m365_client_secret):
        logger.warning("M365 credentials not configured; skipping M365 polling.")
        return

    client = m365.build_client_from_settings()
    try:
        client.start_subscriptions(settings.m365_content_type_list)
    except Exception:
        logger.exception("failed starting M365 subscriptions (they may already be active)")

    lookback_minutes = max(5, settings.m365_poll_interval_seconds // 60 + 2)
    while not _stop_event.is_set():
        try:
            for record in m365.poll_once(client, settings.m365_content_type_list, lookback_minutes):
                _ingest_queue.put(RawItem(source="m365", raw_text=json.dumps(record), parsed=record))
        except Exception:
            logger.exception("M365 poll cycle failed")
        _stop_event.wait(settings.m365_poll_interval_seconds)


async def _on_fortinet_line(line: str) -> None:
    parsed = parse_kv(line)
    if not parsed:
        return
    try:
        _ingest_queue.put_nowait(RawItem(source="fortinet", raw_text=line, parsed=parsed))
    except queue.Full:
        logger.error("ingest queue full; dropping Fortinet log line")


def run_fortinet_listener() -> None:
    async def _serve() -> None:
        protocol = settings.fortinet_syslog_protocol.lower()
        if protocol == "tcp":
            server = await run_tcp_server(settings.fortinet_syslog_host, settings.fortinet_syslog_port, _on_fortinet_line)
            async with server:
                await server.serve_forever()
        else:
            await run_udp_server(settings.fortinet_syslog_host, settings.fortinet_syslog_port, _on_fortinet_line)
            while not _stop_event.is_set():
                await asyncio.sleep(1)

    asyncio.run(_serve())


# --------------------------------------------------------------------------
# Consumer
# --------------------------------------------------------------------------

def process_item(item: RawItem) -> None:
    ev = normalize_m365(item.parsed) if item.source == "m365" else normalize_fortinet(item.parsed)

    with SessionLocal() as session:
        raw_row = store_raw_event(session, item.source, item.raw_text)
        event_row = store_event(session, ev, raw_row.id)
        session.commit()

        matches = evaluate_event(session, ev, cooldown_minutes=settings.alert_cooldown_minutes)
        for matched in matches:
            dispatch_alert(session, matched, [event_row.id], item.source)
        session.commit()


def run_worker() -> None:
    while not _stop_event.is_set():
        try:
            item = _ingest_queue.get(timeout=1)
        except queue.Empty:
            continue
        try:
            process_item(item)
        except Exception:
            logger.exception("failed processing %s event", item.source)


def main() -> None:
    init_db()
    logger.info("Database ready at %s", settings.database_url)

    threads = [
        threading.Thread(target=run_fortinet_listener, name="fortinet-listener", daemon=True),
        threading.Thread(target=run_m365_poller, name="m365-poller", daemon=True),
        threading.Thread(target=run_worker, name="event-worker", daemon=True),
    ]
    for t in threads:
        t.start()

    def _shutdown(*_args: Any) -> None:
        logger.info("shutting down...")
        _stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while not _stop_event.is_set():
        time.sleep(1)


if __name__ == "__main__":
    main()

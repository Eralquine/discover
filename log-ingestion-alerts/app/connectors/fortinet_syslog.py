"""Listens for syslog sent by a FortiGate and hands each raw log line off.

FortiGate emits logs as space-separated key=value pairs (optionally prefixed
with a standard syslog priority/header), e.g.:

    <189>date=2024-01-01 time=12:00:00 devname="FGT1" type="traffic"
    subtype="forward" level="notice" srcip=1.2.3.4 dstip=5.6.7.8
    action="deny" ...

Configure the FortiGate to send here under
Log & Report > Log Settings > Remote Logging (Security Fabric > syslog in
newer firmware). UDP is simplest; prefer TCP+TLS in production since UDP
syslog can silently drop messages under load - see README.
"""
from __future__ import annotations

import asyncio
import logging
import re
import shlex
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

_PRIORITY_RE = re.compile(r"^<\d+>\d*\s*")
# Strips an RFC3164-style "Mon dd hh:mm:ss host " header if a syslog relay adds one
# in front of the FortiGate key=value body.
_RFC3164_HEADER_RE = re.compile(
    r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\S+\s+"
)

MessageHandler = Callable[[str], Awaitable[None]]


def strip_syslog_header(line: str) -> str:
    line = _PRIORITY_RE.sub("", line, count=1)
    line = _RFC3164_HEADER_RE.sub("", line, count=1)
    return line.strip()


def parse_kv(line: str) -> dict[str, Any]:
    """Parses a FortiGate key=value log line into a dict, honoring quoted values."""
    body = strip_syslog_header(line)
    result: dict[str, Any] = {}
    try:
        tokens = shlex.split(body, posix=True)
    except ValueError:
        # Unbalanced quotes etc. - fall back to a naive split so we still
        # capture something rather than dropping the record.
        tokens = body.split()
    for token in tokens:
        if "=" not in token:
            continue
        key, _, value = token.partition("=")
        result[key] = value
    return result


class FortiSyslogServer(asyncio.DatagramProtocol):
    def __init__(self, on_message: MessageHandler, loop: asyncio.AbstractEventLoop) -> None:
        self._on_message = on_message
        self._loop = loop

    def datagram_received(self, data: bytes, addr) -> None:  # noqa: ANN001 - asyncio signature
        try:
            line = data.decode("utf-8", errors="replace")
        except Exception:
            logger.exception("failed decoding syslog datagram from %s", addr)
            return
        self._loop.create_task(self._on_message(line))


async def run_udp_server(host: str, port: int, on_message: MessageHandler) -> asyncio.DatagramTransport:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: FortiSyslogServer(on_message, loop),
        local_addr=(host, port),
    )
    logger.info("Fortinet syslog UDP listener started on %s:%s", host, port)
    return transport


async def _handle_tcp_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, on_message: MessageHandler
) -> None:
    peer = writer.get_extra_info("peername")
    try:
        while not reader.at_eof():
            line = await reader.readline()
            if not line:
                break
            await on_message(line.decode("utf-8", errors="replace"))
    finally:
        logger.debug("Fortinet syslog TCP client disconnected: %s", peer)
        writer.close()


async def run_tcp_server(host: str, port: int, on_message: MessageHandler) -> asyncio.base_events.Server:
    server = await asyncio.start_server(
        lambda r, w: _handle_tcp_client(r, w, on_message), host=host, port=port
    )
    logger.info("Fortinet syslog TCP listener started on %s:%s", host, port)
    return server

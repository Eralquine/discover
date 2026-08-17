"""Rule-based detection engine.

Rules live in rules.yaml so new detections can be added/tuned without
touching code. Two kinds are supported:

  immediate  - a single matching event is itself the alert (e.g. malware
               blocked, external mail forwarding enabled).
  threshold  - N matching events sharing a group field (actor, src_ip, ...)
               within a trailing window trigger the alert (e.g. brute force).

Each rule that fires is deduplicated against recently-sent alerts for the
same rule+group so a sustained attack produces one alert per cooldown
window instead of one per event.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.db import count_recent_events, recent_alert_exists
from app.schema import NormalizedEvent

logger = logging.getLogger(__name__)

RULES_PATH = Path(__file__).parent / "rules.yaml"


@dataclass
class MatchedAlert:
    rule_id: str
    group_key: str
    severity: str
    title: str
    description: str


def load_rules() -> list[dict[str, Any]]:
    with RULES_PATH.open() as f:
        return yaml.safe_load(f)["rules"]


_rules_cache: list[dict[str, Any]] | None = None


def get_rules() -> list[dict[str, Any]]:
    global _rules_cache
    if _rules_cache is None:
        _rules_cache = load_rules()
    return _rules_cache


def evaluate_event(
    session: Session, ev: NormalizedEvent, *, cooldown_minutes: int, now: datetime | None = None
) -> list[MatchedAlert]:
    """Checks a just-stored NormalizedEvent against all rules and returns the ones that fire.

    Assumes `ev` has already been persisted via db.store_event so threshold
    rules can count it among "recent events". `now` defaults to the actual
    current time; tests pass a fixed value so window math is deterministic.
    """
    matches: list[MatchedAlert] = []
    for rule in get_rules():
        if rule["source"] != ev.source or rule["event_type"] != ev.event_type:
            continue

        if rule["kind"] == "immediate":
            group_value = ev.actor or ev.src_ip or "unknown"
            count = 1
        elif rule["kind"] == "threshold":
            group_field = rule["group_field"]
            group_value = getattr(ev, group_field, None)
            if not group_value:
                continue
            count = count_recent_events(
                session,
                source=ev.source,
                event_type=ev.event_type,
                group_field=group_field,
                group_value=group_value,
                window_minutes=rule["window_minutes"],
                now=now,
            )
            if count < rule["threshold"]:
                continue
        else:
            logger.warning("unknown rule kind %r for rule %s", rule["kind"], rule["id"])
            continue

        group_key = f"{rule['id']}:{group_value}"
        if recent_alert_exists(
            session, rule_id=rule["id"], group_key=group_key, cooldown_minutes=cooldown_minutes, now=now
        ):
            continue

        context = {
            "actor": ev.actor or "unknown",
            "src_ip": ev.src_ip or "unknown",
            "dest_ip": ev.dest_ip or "unknown",
            "group_value": group_value,
            "count": count,
            "window_minutes": rule.get("window_minutes", ""),
        }
        matches.append(
            MatchedAlert(
                rule_id=rule["id"],
                group_key=group_key,
                severity=rule["severity"],
                title=rule["title"].format(**context),
                description=rule["description"].format(**context),
            )
        )
    return matches

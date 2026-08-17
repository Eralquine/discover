"""Common normalized event shape that every connector maps its raw logs into.

Keeping every source (Microsoft 365, Fortinet, and whatever gets added next)
funneled through one shape is what lets a single rule engine and alerting
pipeline work across all of them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

SEVERITIES = ("low", "medium", "high", "critical")


@dataclass
class NormalizedEvent:
    source: str  # "m365" | "fortinet"
    event_type: str  # e.g. "signin_failed", "inbox_rule_created", "firewall_denied"
    occurred_at: datetime
    severity: str = "low"
    actor: Optional[str] = None
    src_ip: Optional[str] = None
    dest_ip: Optional[str] = None
    geo_country: Optional[str] = None
    action: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"invalid severity {self.severity!r}, must be one of {SEVERITIES}")
        if self.occurred_at.tzinfo is None:
            self.occurred_at = self.occurred_at.replace(tzinfo=timezone.utc)

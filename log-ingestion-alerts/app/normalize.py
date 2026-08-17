"""Maps raw records from each connector into the common NormalizedEvent shape."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schema import NormalizedEvent

# --------------------------------------------------------------------------
# Microsoft 365 (Office 365 Management Activity API records)
# --------------------------------------------------------------------------

_FORWARDING_PARAMS = {"forwardto", "redirectto", "forwardingsmtpaddress", "forwardingaddress"}


def _m365_param(record: dict[str, Any], name: str) -> Any:
    """Office 365 audit records often nest changed values under a Parameters list
    of {"Name": ..., "Value": ...} instead of top-level keys."""
    for param in record.get("Parameters", []) or []:
        if str(param.get("Name", "")).lower() == name.lower():
            return param.get("Value")
    return record.get(name)


def _m365_has_external_forwarding(record: dict[str, Any]) -> bool:
    for param in record.get("Parameters", []) or []:
        if str(param.get("Name", "")).lower() in _FORWARDING_PARAMS:
            value = param.get("Value")
            if value:
                return True
    return False


def normalize_m365(record: dict[str, Any]) -> NormalizedEvent:
    operation = str(record.get("Operation", ""))
    op_lower = operation.lower()
    result_status = str(record.get("ResultStatus", "")).lower()
    client_ip = record.get("ClientIP") or record.get("ActorIpAddress")
    if client_ip and ":" in client_ip and client_ip.count(":") == 1:
        client_ip = client_ip.split(":")[0]  # strip a trailing :port

    occurred_at_raw = record.get("CreationTime")
    occurred_at = (
        datetime.fromisoformat(occurred_at_raw.replace("Z", "+00:00"))
        if occurred_at_raw
        else datetime.now(timezone.utc)
    )

    event_type = "m365_other"
    severity = "low"

    if op_lower in ("userloginfailed",) or (op_lower == "userloggedin" and result_status == "failed"):
        event_type = "signin_failed"
        severity = "medium"
    elif op_lower == "userloggedin" and result_status in ("", "succeeded", "success"):
        event_type = "signin_success"
        severity = "low"
    elif op_lower in ("new-inboxrule", "set-inboxrule", "set-mailbox"):
        if _m365_has_external_forwarding(record):
            event_type = "mailbox_forwarding_enabled"
            severity = "high"
        else:
            event_type = "inbox_rule_created"
            severity = "medium"
    elif op_lower in ("add member to role.", "add member to role"):
        event_type = "privileged_role_assignment"
        severity = "high"
    elif "malware" in op_lower or op_lower == "phishmail":
        event_type = "mail_threat_detected"
        severity = "high"

    return NormalizedEvent(
        source="m365",
        event_type=event_type,
        occurred_at=occurred_at,
        severity=severity,
        actor=record.get("UserId"),
        src_ip=client_ip,
        geo_country=record.get("Country"),
        action=result_status or None,
        details={"operation": operation, "workload": record.get("Workload")},
        raw=record,
    )


# --------------------------------------------------------------------------
# Fortinet FortiGate (parsed key=value syslog)
# --------------------------------------------------------------------------

_IPS_VIRUS_TYPES = {"ips", "virus", "anomaly"}


def _fortinet_timestamp(fields: dict[str, Any]) -> datetime:
    if "eventtime" in fields:
        try:
            # FortiGate eventtime is often nanoseconds since epoch; fall back to seconds.
            raw = int(fields["eventtime"])
            if raw > 10**14:
                raw //= 10**9
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        except (ValueError, OverflowError):
            pass
    date_str, time_str = fields.get("date"), fields.get("time")
    if date_str and time_str:
        try:
            return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def normalize_fortinet(fields: dict[str, Any]) -> NormalizedEvent:
    log_type = fields.get("type", "")
    subtype = fields.get("subtype", "")
    action = fields.get("action", "")

    event_type = "fortinet_other"
    severity = "low"

    if log_type == "traffic":
        if action in ("deny", "drop", "block"):
            event_type = "firewall_denied"
            severity = "low"  # volume-based escalation happens in the rule engine
        else:
            event_type = "firewall_allowed"
            severity = "low"
    elif log_type == "utm":
        if subtype == "virus":
            event_type = "malware_block"
            severity = "critical"
        elif subtype == "ips":
            event_type = "ips_block" if action in ("block", "dropped", "clear_session") else "ips_detected"
            severity = "high" if event_type == "ips_block" else "medium"
        elif subtype == "webfilter" and action in ("block", "blocked"):
            event_type = "web_block"
            severity = "medium"
        elif subtype == "app-ctrl":
            event_type = "app_control"
            severity = "medium"
    elif log_type == "vpn":
        event_type = "vpn_login_failed" if fields.get("status") in ("failed", "failure") else "vpn_login"
        severity = "medium" if event_type == "vpn_login_failed" else "low"
    elif log_type == "event" and subtype == "system":
        event_type = "system_event"
        severity = "low"

    return NormalizedEvent(
        source="fortinet",
        event_type=event_type,
        occurred_at=_fortinet_timestamp(fields),
        severity=severity,
        actor=fields.get("user") or None,
        src_ip=fields.get("srcip"),
        dest_ip=fields.get("dstip"),
        geo_country=fields.get("srccountry"),
        action=action or None,
        details={"logid": fields.get("logid"), "policyid": fields.get("policyid"), "service": fields.get("service")},
        raw=fields,
    )

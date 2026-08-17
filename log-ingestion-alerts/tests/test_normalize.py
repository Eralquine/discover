import json
from pathlib import Path

from app.normalize import normalize_fortinet, normalize_m365
from app.connectors.fortinet_syslog import parse_kv

FIXTURES = Path(__file__).parent / "fixtures"


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _load_log_line(name: str) -> str:
    return (FIXTURES / name).read_text().strip()


def test_normalize_m365_signin_failed():
    record = _load_json("m365_signin_failed.json")
    ev = normalize_m365(record)

    assert ev.source == "m365"
    assert ev.event_type == "signin_failed"
    assert ev.severity == "medium"
    assert ev.actor == "someone@example.com"
    assert ev.src_ip == "203.0.113.42"  # port stripped


def test_normalize_m365_mailbox_forwarding_is_high_severity():
    record = _load_json("m365_mailbox_forwarding.json")
    ev = normalize_m365(record)

    assert ev.event_type == "mailbox_forwarding_enabled"
    assert ev.severity == "high"
    assert ev.actor == "victim@example.com"


def test_normalize_fortinet_denied_traffic():
    line = _load_log_line("fortinet_denied.log")
    fields = parse_kv(line)
    ev = normalize_fortinet(fields)

    assert ev.source == "fortinet"
    assert ev.event_type == "firewall_denied"
    assert ev.src_ip == "198.51.100.99"
    assert ev.dest_ip == "192.0.2.10"
    assert ev.geo_country == "Netherlands"


def test_normalize_fortinet_ips_block_is_high_severity():
    line = _load_log_line("fortinet_ips_block.log")
    fields = parse_kv(line)
    ev = normalize_fortinet(fields)

    assert ev.event_type == "ips_block"
    assert ev.severity == "high"


def test_parse_kv_strips_syslog_priority_and_handles_quotes():
    fields = parse_kv('<189>date=2026-08-17 time=10:30:00 devname="FGT EDGE 1" action="deny"')
    assert fields["date"] == "2026-08-17"
    assert fields["devname"] == "FGT EDGE 1"
    assert fields["action"] == "deny"

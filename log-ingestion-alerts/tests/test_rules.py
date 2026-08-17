from datetime import timedelta

from app.db import Alert, store_event
from app.rules import evaluate_event
from app.schema import NormalizedEvent


def _signin_failed(now, actor="someone@example.com", offset_seconds=0):
    return NormalizedEvent(
        source="m365",
        event_type="signin_failed",
        occurred_at=now + timedelta(seconds=offset_seconds),
        severity="medium",
        actor=actor,
        src_ip="203.0.113.42",
    )


def test_immediate_rule_fires_once(session, now):
    ev = NormalizedEvent(
        source="m365",
        event_type="mailbox_forwarding_enabled",
        occurred_at=now,
        severity="high",
        actor="victim@example.com",
        src_ip="198.51.100.7",
    )
    store_event(session, ev, raw_event_id=None)
    session.commit()

    matches = evaluate_event(session, ev, cooldown_minutes=30, now=now)
    assert len(matches) == 1
    assert matches[0].rule_id == "m365_mailbox_forwarding"


def test_threshold_rule_needs_enough_events_in_window(session, now):
    matches = []
    for i in range(5):
        ev = _signin_failed(now, offset_seconds=i)
        store_event(session, ev, raw_event_id=None)
        session.commit()
        matches = evaluate_event(session, ev, cooldown_minutes=30, now=now)
        if i < 4:
            assert matches == [], f"rule should not fire before the threshold (attempt {i + 1})"

    assert len(matches) == 1
    assert matches[0].rule_id == "m365_brute_force"
    assert "5 failed" in matches[0].description


def test_cooldown_suppresses_repeat_alert(session, now):
    for i in range(5):
        ev = _signin_failed(now, offset_seconds=i)
        store_event(session, ev, raw_event_id=None)
    session.commit()

    ev = _signin_failed(now, offset_seconds=5)
    store_event(session, ev, raw_event_id=None)
    session.commit()
    matches = evaluate_event(session, ev, cooldown_minutes=30, now=now)
    assert len(matches) == 1

    # Simulate the alert having been recorded (what alerting.dispatch_alert does).
    session.add(
        Alert(
            rule_id=matches[0].rule_id,
            group_key=matches[0].group_key,
            severity=matches[0].severity,
            title=matches[0].title,
            description=matches[0].description,
            event_ids=[],
        )
    )
    session.commit()

    # A 6th failed sign-in still exceeds the threshold, but the cooldown
    # should suppress firing again immediately.
    ev6 = _signin_failed(now, offset_seconds=6)
    store_event(session, ev6, raw_event_id=None)
    session.commit()
    matches_again = evaluate_event(session, ev6, cooldown_minutes=30, now=now)
    assert matches_again == []


def test_different_actor_does_not_share_threshold_count(session, now):
    for i in range(3):
        ev = _signin_failed(now, actor="alice@example.com", offset_seconds=i)
        store_event(session, ev, raw_event_id=None)
    for i in range(3):
        ev = _signin_failed(now, actor="bob@example.com", offset_seconds=i)
        store_event(session, ev, raw_event_id=None)
    session.commit()

    matches = evaluate_event(session, ev, cooldown_minutes=30, now=now)
    assert matches == []  # only 3 events each, threshold is 5

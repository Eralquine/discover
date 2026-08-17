from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, DateTime, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import settings
from app.schema import NormalizedEvent


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class RawEvent(Base):
    __tablename__ = "raw_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(32))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    payload: Mapped[str] = mapped_column(Text)  # raw text/JSON exactly as received, for forensics


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    raw_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    severity: Mapped[str] = mapped_column(String(16))
    actor: Mapped[str | None] = mapped_column(String(256), nullable=True)
    src_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dest_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geo_country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Client(Base):
    """A downstream party alerts should be forwarded to (e.g. an MSSP customer)."""

    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(256))
    contact_emails: Mapped[str] = mapped_column(Text)  # comma-separated
    # Only forward alerts whose event source/actor/etc. match this client;
    # empty string means "forward everything".
    match_source: Mapped[str] = mapped_column(String(32), default="")
    active: Mapped[bool] = mapped_column(default=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    rule_id: Mapped[str] = mapped_column(String(64))
    group_key: Mapped[str] = mapped_column(String(256))  # what this alert was deduplicated/cooled-down on
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    event_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


_engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(_engine)


def store_raw_event(session: Session, source: str, payload: str) -> RawEvent:
    raw = RawEvent(source=source, payload=payload)
    session.add(raw)
    session.flush()
    return raw


def store_event(session: Session, ev: NormalizedEvent, raw_event_id: str | None) -> Event:
    row = Event(
        raw_event_id=raw_event_id,
        source=ev.source,
        event_type=ev.event_type,
        occurred_at=ev.occurred_at,
        severity=ev.severity,
        actor=ev.actor,
        src_ip=ev.src_ip,
        dest_ip=ev.dest_ip,
        geo_country=ev.geo_country,
        action=ev.action,
        details=ev.details,
    )
    session.add(row)
    session.flush()
    return row


def count_recent_events(
    session: Session,
    *,
    source: str,
    event_type: str,
    group_field: str,
    group_value: str,
    window_minutes: int,
    now: datetime | None = None,
) -> int:
    """Count events matching source/event_type/group field within a trailing window.

    group_field must be one of the concrete Event columns (actor, src_ip, ...).
    """
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(minutes=window_minutes)
    column = getattr(Event, group_field)
    stmt = select(Event).where(
        Event.source == source,
        Event.event_type == event_type,
        column == group_value,
        Event.occurred_at >= since,
    )
    return len(session.execute(stmt).scalars().all())


def recent_alert_exists(session: Session, *, rule_id: str, group_key: str, cooldown_minutes: int, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(minutes=cooldown_minutes)
    stmt = select(Alert).where(
        Alert.rule_id == rule_id,
        Alert.group_key == group_key,
        Alert.created_at >= since,
    )
    return session.execute(stmt).scalars().first() is not None


def list_active_clients(session: Session) -> list[Client]:
    return list(session.execute(select(Client).where(Client.active.is_(True))).scalars().all())

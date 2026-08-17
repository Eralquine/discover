"""Turns a matched rule into an outbound email: to the internal SOC inbox,
and forwarded on to any client configured to receive alerts from that source.
"""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Alert, list_active_clients
from app.rules import MatchedAlert

logger = logging.getLogger(__name__)

_SEVERITY_COLOR = {
    "low": "#6b7280",
    "medium": "#d97706",
    "high": "#dc2626",
    "critical": "#7f1d1d",
}

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html"]),
)


def render_alert_email(alert: Alert) -> str:
    template = _env.get_template("alert_email.html.j2")
    return template.render(
        title=alert.title,
        description=alert.description,
        severity=alert.severity,
        severity_color=_SEVERITY_COLOR.get(alert.severity, "#1a1a1a"),
        rule_id=alert.rule_id,
        created_at=alert.created_at.isoformat(),
        event_count=len(alert.event_ids),
    )


def send_email(subject: str, html_body: str, recipients: list[str]) -> None:
    if not recipients:
        return
    if not settings.smtp_host:
        logger.warning("SMTP not configured; skipping send of %r to %s", subject, recipients)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.alert_from_address
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.alert_from_address, recipients, msg.as_string())


def _client_recipients(session: Session, source: str) -> list[str]:
    recipients: list[str] = []
    for client in list_active_clients(session):
        if client.match_source and client.match_source != source:
            continue
        recipients.extend(e.strip() for e in client.contact_emails.split(",") if e.strip())
    return recipients


def dispatch_alert(session: Session, matched: MatchedAlert, event_ids: list[str], source: str) -> Alert:
    """Persists the alert and emails the internal team plus any matching clients."""
    alert = Alert(
        rule_id=matched.rule_id,
        group_key=matched.group_key,
        severity=matched.severity,
        title=matched.title,
        description=matched.description,
        event_ids=event_ids,
    )
    session.add(alert)
    session.flush()

    html_body = render_alert_email(alert)
    subject = f"[{matched.severity.upper()}] {matched.title}"

    recipients = list(settings.alert_internal_recipient_list)
    recipients.extend(_client_recipients(session, source))
    # de-dupe while preserving order
    recipients = list(dict.fromkeys(recipients))

    try:
        send_email(subject, html_body, recipients)
        alert.sent_at = datetime.now(timezone.utc)
    except Exception:
        logger.exception("failed sending alert email for rule %s", matched.rule_id)

    session.flush()
    return alert

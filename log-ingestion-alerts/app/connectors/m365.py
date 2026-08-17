"""Pulls audit records from the Office 365 Management Activity API.

This is the API Microsoft ships specifically for SIEM-style ingestion: it
covers Entra ID (Azure AD) sign-ins/directory changes, Exchange Online
(including mailbox rule and mail-forwarding changes), SharePoint, and more,
all from a single feed - which is why it's used here instead of stitching
together several separate Graph endpoints.

Setup (see README for full walkthrough):
  1. Register an app in Entra ID.
  2. Grant it the Application permission "ActivityFeed.Read" under
     "Office 365 Management APIs", with admin consent.
  3. Start a subscription per content type once:
       POST https://manage.office.com/api/v1.0/{tenant}/activity/feed/subscriptions/start?contentType={type}
     (start_subscriptions() below does this.)
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import msal

from app.config import settings

logger = logging.getLogger(__name__)

_AUTHORITY = "https://login.microsoftonline.com/{tenant}"
_RESOURCE = "https://manage.office.com"
_BASE = "https://manage.office.com/api/v1.0/{tenant}"


class M365Client:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str) -> None:
        self.tenant_id = tenant_id
        self._app = msal.ConfidentialClientApplication(
            client_id,
            authority=_AUTHORITY.format(tenant=tenant_id),
            client_credential=client_secret,
        )

    def _token(self) -> str:
        result = self._app.acquire_token_silent([f"{_RESOURCE}/.default"], account=None)
        if not result:
            result = self._app.acquire_token_for_client(scopes=[f"{_RESOURCE}/.default"])
        if "access_token" not in result:
            raise RuntimeError(f"failed to acquire M365 token: {result.get('error_description', result)}")
        return result["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token()}"}

    def start_subscriptions(self, content_types: list[str]) -> None:
        base = _BASE.format(tenant=self.tenant_id)
        with httpx.Client(timeout=30) as client:
            for content_type in content_types:
                resp = client.post(
                    f"{base}/activity/feed/subscriptions/start",
                    params={"contentType": content_type},
                    headers=self._headers(),
                )
                if resp.status_code not in (200, 400):  # 400 = already started, treat as fine
                    resp.raise_for_status()

    def list_available_content(
        self, content_type: str, start_time: datetime, end_time: datetime
    ) -> Iterator[dict[str, Any]]:
        """Yields content blob descriptors {"contentUri": ..., "contentId": ...} available in the window."""
        base = _BASE.format(tenant=self.tenant_id)
        url = f"{base}/activity/feed/subscriptions/content"
        params = {
            "contentType": content_type,
            "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        with httpx.Client(timeout=30) as client:
            while url:
                resp = client.get(url, params=params, headers=self._headers())
                resp.raise_for_status()
                yield from resp.json()
                url = resp.links.get("next", {}).get("url")
                params = None  # next-page URL already has the query string

    def fetch_content(self, content_uri: str) -> list[dict[str, Any]]:
        """Fetches the actual audit records referenced by a content descriptor."""
        with httpx.Client(timeout=30) as client:
            resp = client.get(content_uri, headers=self._headers())
            resp.raise_for_status()
            return resp.json()


def poll_once(client: M365Client, content_types: list[str], lookback_minutes: int) -> Iterator[dict[str, Any]]:
    """One polling pass: yields raw audit record dicts across all subscribed content types."""
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=lookback_minutes)
    for content_type in content_types:
        try:
            for descriptor in client.list_available_content(content_type, start_time, end_time):
                try:
                    for record in client.fetch_content(descriptor["contentUri"]):
                        yield record
                except httpx.HTTPError:
                    logger.exception("failed fetching content blob %s", descriptor.get("contentId"))
        except httpx.HTTPError:
            logger.exception("failed listing available content for %s", content_type)


def build_client_from_settings() -> M365Client:
    return M365Client(settings.m365_tenant_id, settings.m365_client_id, settings.m365_client_secret)

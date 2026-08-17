"""Registers (or updates) a client that alerts should be forwarded to.

Usage:
    python -m scripts.add_client --name "Acme Corp" --emails soc@acme.com,ciso@acme.com [--source fortinet]

Omit --source to forward every alert (both Microsoft 365 and Fortinet) to this client.
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db import Client, SessionLocal, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--emails", required=True, help="comma-separated contact emails")
    parser.add_argument("--source", choices=["m365", "fortinet"], default="", help="omit to forward all sources")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as session:
        existing = session.execute(select(Client).where(Client.name == args.name)).scalar_one_or_none()
        if existing:
            existing.contact_emails = args.emails
            existing.match_source = args.source
            existing.active = True
            print(f"Updated client {args.name!r}")
        else:
            session.add(Client(name=args.name, contact_emails=args.emails, match_source=args.source))
            print(f"Created client {args.name!r}")
        session.commit()


if __name__ == "__main__":
    main()

"""Celery periodic task: email members of a subscription shortly before it expires.

Runs on the same Celery app as media processing (src.infrastructure.media.celery_app)
via Celery Beat, on the "default" queue. Builds its own small sync SQLAlchemy
engine from SYNC_DATABASE_URL — there is no shared SyncSessionFactory in this
codebase to reuse (see media_tasks.py's _get_media_sync for the closest analog,
which follows the same "build a sync session inline" approach).
"""
from __future__ import annotations

import asyncio
import logging
import os

from sqlalchemy import create_engine, text

from src.infrastructure.media.celery_app import celery_app

log = logging.getLogger(__name__)

# Reminder window: subscriptions expiring within this many hours (and not yet
# reminded) get emailed on the next beat tick. A short-lived promo (e.g. a
# 3-hour flash sale) falls inside this window immediately at creation, so it
# effectively gets its reminder right away rather than 24h out.
REMINDER_WINDOW_HOURS = 24


def _get_sync_engine():
    url = os.environ.get("SYNC_DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/ourfamroots")
    return create_engine(url, pool_pre_ping=True)


@celery_app.task(name="src.infrastructure.subscriptions.subscription_tasks.send_expiry_reminders")
def send_expiry_reminders() -> dict:
    """Find soon-to-expire, not-yet-reminded subscriptions and email their members."""
    # Deferred imports to avoid circular import at Celery module-load time
    # (src.api.v1.subscriptions imports FastAPI machinery we don't want
    # pulled into the worker's import graph unconditionally).
    from src.api.v1.subscriptions import AVAILABLE_FILTERS  # noqa: PLC0415
    from src.infrastructure.email.service import send_email, subscription_expiring_email  # noqa: PLC0415

    filter_labels_by_key = {f["key"]: f["label"] for f in AVAILABLE_FILTERS}

    engine = _get_sync_engine()
    reminded = 0
    emails_sent = 0

    with engine.connect() as conn:
        subs = conn.execute(text("""
            SELECT id, name, expires_at
            FROM subscriptions
            WHERE expires_at IS NOT NULL
              AND reminder_sent_at IS NULL
              AND expires_at > now()
              AND expires_at <= now() + make_interval(hours => :window_hours)
        """), {"window_hours": REMINDER_WINDOW_HOURS}).fetchall()

        for sub in subs:
            members = conn.execute(text("""
                SELECT u.email,
                       COALESCE(NULLIF(TRIM(CONCAT(u.given_name, ' ', u.family_name)), ''), u.email) AS display_name
                FROM subscription_members sm
                JOIN users u ON u.id = sm.user_id
                WHERE sm.subscription_id = :sid
            """), {"sid": sub.id}).fetchall()

            filter_keys = conn.execute(text(
                "SELECT filter_key FROM subscription_filters WHERE subscription_id = :sid"
            ), {"sid": sub.id}).scalars().all()
            filter_labels = [filter_labels_by_key.get(k, k) for k in filter_keys]

            expires_display = sub.expires_at.strftime("%b %d, %Y at %I:%M %p UTC")

            for member in members:
                html, text_body = subscription_expiring_email(
                    display_name=member.display_name,
                    subscription_name=sub.name,
                    expires_at_display=expires_display,
                    filter_labels=filter_labels,
                )
                try:
                    asyncio.run(send_email(
                        to=member.email,
                        subject=f"Your {sub.name} subscription is expiring soon",
                        html_body=html,
                        text_body=text_body,
                    ))
                    emails_sent += 1
                except Exception:
                    log.exception("send_expiry_reminders: failed to email %s for subscription %s", member.email, sub.id)

            conn.execute(text(
                "UPDATE subscriptions SET reminder_sent_at = now() WHERE id = :sid"
            ), {"sid": sub.id})
            conn.commit()
            reminded += 1

    log.info("send_expiry_reminders done: subscriptions_reminded=%s emails_sent=%s", reminded, emails_sent)
    return {"subscriptions_reminded": reminded, "emails_sent": emails_sent}

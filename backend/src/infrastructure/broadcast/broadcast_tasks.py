"""Celery task: actually send a broadcast email's messages.

Runs on the same Celery app as media processing (src.infrastructure.media.
celery_app), on the "default" queue. The API layer (src/api/v1/broadcast.py)
resolves recipients and writes the BroadcastLogModel row up front (with
sent_count=0/failed_count=0) before enqueueing this task, so the admin's HTTP
request returns immediately instead of waiting for every SMTP send.

Builds its own small sync SQLAlchemy engine from SYNC_DATABASE_URL to update
the log row afterward — there is no shared sync session factory in this
codebase (the API itself is fully async); this follows the same "build a sync
engine inline" approach as subscription_tasks.py's _get_sync_engine, just
with the ORM session instead of raw SQL since BroadcastLogModel already
exists as a mapped class.
"""
from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.infrastructure.media.celery_app import celery_app

log = logging.getLogger(__name__)


def _get_sync_engine():
    url = os.environ.get("SYNC_DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/ourfamroots")
    return create_engine(url, pool_pre_ping=True)


@celery_app.task(name="src.infrastructure.broadcast.broadcast_tasks.send_broadcast_task")
def send_broadcast_task(
    log_id: str,
    recipients: list[dict],
    subject: str,
    body: str,
    category: str,
) -> dict:
    """Send *subject*/*body* to every recipient, then record final counts.

    *recipients* is a list of {"email": str, "full_name": str} dicts resolved
    by the API layer at enqueue time — this task does not re-query eligibility
    (an unsubscribe landing mid-send is an acceptable, rare edge case, not
    worth a second DB round-trip for).
    """
    from src.config import get_settings  # noqa: PLC0415
    from src.infrastructure.database.models.broadcast_log import BroadcastLogModel  # noqa: PLC0415
    from src.infrastructure.email.service import broadcast_email, send_smtp_blocking  # noqa: PLC0415

    settings = get_settings()
    unsubscribe_url = f"{settings.frontend_base_url}/settings/notifications"

    sent = 0
    failed = 0

    for recipient in recipients:
        html, text_body = broadcast_email(
            subject=subject,
            body=body,
            recipient_name=recipient["full_name"],
            category=category,
            unsubscribe_url=unsubscribe_url,
        )
        try:
            send_smtp_blocking(recipient["email"], subject, html, text_body)
            sent += 1
        except Exception:
            log.exception("send_broadcast_task: failed to email %s", recipient["email"])
            failed += 1

    engine = _get_sync_engine()
    with Session(engine) as session:
        row = session.get(BroadcastLogModel, uuid.UUID(log_id))
        if row is not None:
            row.sent_count = sent
            row.failed_count = failed
            session.commit()

    log.info("broadcast.task_done", log_id=log_id, sent=sent, failed=failed)
    return {"sent": sent, "failed": failed}

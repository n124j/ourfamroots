"""Celery application factory for the media worker."""
from __future__ import annotations

import os

from celery import Celery

# ── Create app ─────────────────────────────────────────────────────────────────

celery_app = Celery("ourfamroots_media")

celery_app.conf.update(
    # ── Broker / backend ──────────────────────────────────────────────────────
    broker_url=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    broker_connection_retry_on_startup=True,

    # ── Serialisation ─────────────────────────────────────────────────────────
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # ── Routing — all media tasks go to the dedicated queue ───────────────────
    task_routes={
        "src.infrastructure.media.media_tasks.*": {"queue": "media"},
    },
    task_default_queue="default",

    # ── Worker settings ───────────────────────────────────────────────────────
    worker_prefetch_multiplier=1,          # one task at a time per worker slot
    worker_max_tasks_per_child=50,         # recycle to prevent Pillow memory leaks

    # ── Time limits ───────────────────────────────────────────────────────────
    task_soft_time_limit=120,              # SoftTimeLimitExceeded raised at 120s
    task_time_limit=180,                   # SIGKILL at 180s

    # ── Result expiry ─────────────────────────────────────────────────────────
    result_expires=3600,                   # keep task results for 1 hour

    # ── Beat schedule ──────────────────────────────────────────────────────────
    beat_schedule={
        "send-subscription-expiry-reminders": {
            "task": "src.infrastructure.subscriptions.subscription_tasks.send_expiry_reminders",
            "schedule": 900.0,  # every 15 minutes
        },
    },
)

# Auto-discover tasks in these packages
celery_app.autodiscover_tasks(["src.infrastructure.media", "src.infrastructure.subscriptions"])

# Explicit import so the worker/beat process (started via `-A
# src.infrastructure.media.celery_app`) actually registers this task —
# autodiscover_tasks() only looks for a `tasks` submodule by default, which
# doesn't match this package's `subscription_tasks.py` filename.
from src.infrastructure.subscriptions import subscription_tasks  # noqa: F401,E402

"""Shared helper for writing admin actions to the activity feed (login_events table)."""
from __future__ import annotations

import uuid

from src.infrastructure.database.models.login_event import LoginEventModel

# All event_type values that are stored in login_events (not audit_logs).
# Keep in sync with ActivityPage.tsx ACTION_OPTIONS.
LOGIN_EVENT_TYPES = frozenset({
    "LOGIN", "FAILED_LOGIN", "LOGOUT",
    # User management
    "ADMIN_CREATE", "ADMIN_VERIFY", "ADMIN_UNVERIFY",
    "ADMIN_DEACTIVATE", "ADMIN_ACTIVATE", "ADMIN_UPDATE",
    # Permission group management
    "PG_CREATE", "PG_UPDATE", "PG_DELETE",
    "PG_ADD_TREE", "PG_REMOVE_TREE",
    "PG_ADD_MEMBER", "PG_REMOVE_MEMBER",
    # Broadcast
    "BROADCAST_SEND", "BROADCAST_DEL",
})


async def log_admin_action(
    session,
    tenant_id: uuid.UUID,
    admin_id: uuid.UUID,
    admin_name: str,
    event_type: str,
    target_display: str,
    ip_address: str | None = None,
) -> None:
    """Write an admin action to login_events so it appears in the activity feed.

    *target_display* is stored in the user_email field and shown as the
    entity description in the activity feed.
    """
    session.add(LoginEventModel(
        tenant_id=tenant_id,
        user_id=admin_id,
        user_display_name=admin_name,
        user_email=target_display,
        event_type=event_type,
        success=True,
        ip_address=ip_address,
    ))

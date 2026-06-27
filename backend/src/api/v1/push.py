"""Web Push subscription API + utility for sending push notifications."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUserDep, UoWDep
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["push"])


# ── Schemas ────────────────────────────────────────────────────────────────

class PushSubscriptionRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/push/vapid-public-key")
async def vapid_public_key() -> dict:
    """Return the VAPID public key so the browser can subscribe."""
    return {"vapid_public_key": get_settings().vapid_public_key}


@router.post("/push/subscribe", status_code=status.HTTP_204_NO_CONTENT, response_model=None, response_class=Response)
async def subscribe(
    body: PushSubscriptionRequest,
    request: Request,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> None:
    ua = body.user_agent or request.headers.get("user-agent", "")[:512]
    await uow._session.execute(
        text("""
            INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, user_agent)
            VALUES (:uid, :endpoint, :p256dh, :auth, :ua)
            ON CONFLICT (user_id, endpoint) DO UPDATE
                SET p256dh = EXCLUDED.p256dh,
                    auth   = EXCLUDED.auth,
                    user_agent = EXCLUDED.user_agent
        """),
        {"uid": current_user.id, "endpoint": body.endpoint, "p256dh": body.p256dh, "auth": body.auth, "ua": ua},
    )
    await uow._session.commit()


@router.delete("/push/unsubscribe", status_code=status.HTTP_204_NO_CONTENT, response_model=None, response_class=Response)
async def unsubscribe(
    body: PushSubscriptionRequest,
    current_user: CurrentUserDep,
    uow: UoWDep,
) -> None:
    await uow._session.execute(
        text("DELETE FROM push_subscriptions WHERE user_id = :uid AND endpoint = :ep"),
        {"uid": current_user.id, "ep": body.endpoint},
    )
    await uow._session.commit()


# ── Push utility ──────────────────────────────────────────────────────────

async def send_push_to_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> None:
    """Fire-and-forget: send a Web Push notification to all subscriptions for user_id."""
    settings = get_settings()
    if not settings.vapid_private_key or not settings.vapid_public_key:
        return

    rows = (await session.execute(
        text("SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = :uid"),
        {"uid": user_id},
    )).fetchall()
    if not rows:
        return

    payload = json.dumps({"title": title, "body": body, "data": data or {}})

    try:
        from pywebpush import webpush, WebPushException
        import base64
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization

        # Reconstruct PEM private key from raw base64url scalar
        raw = base64.urlsafe_b64decode(settings.vapid_private_key + "==")
        private_key = ec.derive_private_key(
            int.from_bytes(raw, "big"), ec.SECP256R1()
        )
        pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

        stale_endpoints: list[str] = []
        for row in rows:
            try:
                webpush(
                    subscription_info={
                        "endpoint": row.endpoint,
                        "keys": {"p256dh": row.p256dh, "auth": row.auth},
                    },
                    data=payload,
                    vapid_private_key=pem,
                    vapid_claims={
                        "sub": f"mailto:{settings.vapid_claims_email}",
                    },
                )
            except WebPushException as exc:
                status_code = getattr(exc.response, "status_code", None)
                if status_code in (404, 410):
                    stale_endpoints.append(row.endpoint)
                else:
                    logger.warning("Push failed for %s: %s", row.endpoint[:60], exc)
            except Exception as exc:
                logger.warning("Push error: %s", exc)

        if stale_endpoints:
            await session.execute(
                text("DELETE FROM push_subscriptions WHERE endpoint = ANY(:eps)"),
                {"eps": stale_endpoints},
            )
            await session.commit()

    except ImportError:
        logger.warning("pywebpush not installed; skipping push delivery")
    except Exception as exc:
        logger.exception("Unexpected push error: %s", exc)

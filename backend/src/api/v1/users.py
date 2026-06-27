"""Users router — /api/v1/users/*"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel

from src.api.deps import (
    HasherDep,
    SessionDep,
    TokenStoreDep,
    UoWDep,
    VerifiedUserDep,
)
from src.application.users.schemas import UpdateUserRequest, UserProfileResponse
from src.application.users.service import UserService
from src.application.auth.schemas import ChangePasswordRequest

router = APIRouter(prefix="/users", tags=["Users"])

ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB


class ConfirmDeletionRequest(BaseModel):
    token: str


def _get_user_service(uow: UoWDep, token_store: TokenStoreDep, hasher: HasherDep) -> UserService:
    return UserService(uow=uow, token_store=token_store, hasher=hasher)


def _presign_avatar(profile: UserProfileResponse) -> UserProfileResponse:
    """Presign S3 avatar keys; leave full URLs (OAuth) and None untouched."""
    url = profile.avatar_url
    if url and not url.startswith("http"):
        from src.api.v1._s3 import presign_photo
        profile.avatar_url = presign_photo(url)
    return profile


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get the authenticated user's profile",
)
async def get_me(
    user: VerifiedUserDep,
    uow: UoWDep,
    token_store: TokenStoreDep,
    hasher: HasherDep,
) -> UserProfileResponse:
    svc = UserService(uow=uow, token_store=token_store, hasher=hasher)
    return _presign_avatar(await svc.get_me(user.id, user.tenant_id))


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    summary="Update the authenticated user's profile",
)
async def update_me(
    req: UpdateUserRequest,
    user: VerifiedUserDep,
    uow: UoWDep,
    token_store: TokenStoreDep,
    hasher: HasherDep,
) -> UserProfileResponse:
    svc = UserService(uow=uow, token_store=token_store, hasher=hasher)
    return _presign_avatar(await svc.update_me(user.id, user.tenant_id, req))


@router.post(
    "/me/avatar",
    summary="Upload a profile picture",
    description="Upload a profile picture for the authenticated user. "
                "Accepts JPEG, PNG, WEBP, or GIF (max 5 MB). "
                "Returns the presigned URL of the uploaded image. "
                "OAuth users (Google, GitHub) cannot use this endpoint — their avatar "
                "is managed by the provider (returns 403).",
    responses={
        200: {"description": "Avatar uploaded", "content": {"application/json": {"example": {"avatar_url": "https://..."}}}},
        403: {"description": "OAuth users cannot change their avatar"},
        413: {"description": "File exceeds 5 MB"},
        415: {"description": "Unsupported image type"},
    },
)
async def upload_avatar(
    user: VerifiedUserDep,
    session: SessionDep,
    file: UploadFile = File(...),
):
    import boto3
    from botocore.config import Config as BotoCfg
    from sqlalchemy import select as sa_select, text as sa_text
    from src.config import get_settings
    from src.infrastructure.database.models.user import UserOAuthProviderModel

    has_oauth = (await session.execute(
        sa_select(UserOAuthProviderModel.id).where(UserOAuthProviderModel.user_id == user.id).limit(1)
    )).first()
    if has_oauth:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Profile picture is managed by your OAuth provider")

    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only JPEG, PNG, WEBP or GIF images are allowed")

    data = await file.read()
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 5 MB limit")

    settings = get_settings()
    ext = (file.filename or "avatar").rsplit(".", 1)[-1].lower()
    key = f"tenants/{user.tenant_id}/users/{user.id}/avatar/{uuid.uuid4()}.{ext}"

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.aws_access_key_id or "minioadmin",
        aws_secret_access_key=settings.aws_secret_access_key or "minioadmin",
        region_name=settings.aws_region,
        config=BotoCfg(signature_version="s3v4"),
    )
    bucket = settings.s3_bucket or "ourfamroots-local"
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=file.content_type)

    await session.execute(
        sa_text("UPDATE users SET avatar_url = :url WHERE id = :uid AND tenant_id = :tid"),
        {"url": key, "uid": user.id, "tid": user.tenant_id},
    )
    await session.commit()

    from src.api.v1._s3 import presign_photo
    return {"avatar_url": presign_photo(key)}


@router.delete(
    "/me/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Remove profile picture",
    description="Remove the authenticated user's profile picture. "
                "OAuth users (Google, GitHub) cannot use this endpoint — their avatar "
                "is managed by the provider (returns 403).",
    responses={
        204: {"description": "Avatar removed"},
        403: {"description": "OAuth users cannot change their avatar"},
    },
)
async def remove_avatar(
    user: VerifiedUserDep,
    session: SessionDep,
):
    from sqlalchemy import select as sa_select, text as sa_text
    from src.infrastructure.database.models.user import UserOAuthProviderModel

    has_oauth = (await session.execute(
        sa_select(UserOAuthProviderModel.id).where(UserOAuthProviderModel.user_id == user.id).limit(1)
    )).first()
    if has_oauth:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Profile picture is managed by your OAuth provider")

    await session.execute(
        sa_text("UPDATE users SET avatar_url = NULL WHERE id = :uid AND tenant_id = :tid"),
        {"uid": user.id, "tid": user.tenant_id},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/me/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Change the authenticated user's password",
)
async def change_password(
    req: ChangePasswordRequest,
    user: VerifiedUserDep,
    uow: UoWDep,
    token_store: TokenStoreDep,
    hasher: HasherDep,
) -> None:
    svc = UserService(uow=uow, token_store=token_store, hasher=hasher)
    await svc.change_password(user.id, user.tenant_id, req.current_password, req.new_password)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Soft-delete the authenticated user's account",
)
async def delete_account(
    password: str,  # passed as query param for simplicity; use request body in production
    user: VerifiedUserDep,
    uow: UoWDep,
    token_store: TokenStoreDep,
    hasher: HasherDep,
) -> None:
    svc = UserService(uow=uow, token_store=token_store, hasher=hasher)
    await svc.delete_account(user.id, user.tenant_id, password)


@router.post(
    "/me/request-deletion",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Request account deletion — sends a confirmation email",
)
async def request_deletion(
    user: VerifiedUserDep,
    uow: UoWDep,
    token_store: TokenStoreDep,
    hasher: HasherDep,
) -> None:
    svc = UserService(uow=uow, token_store=token_store, hasher=hasher)
    await svc.request_deletion(user.id, user.tenant_id)


@router.put(
    "/me/broadcast-subscription",
    summary="Update broadcast email subscription preference",
)
async def update_broadcast_subscription(
    body: dict,
    user: VerifiedUserDep,
    session: SessionDep,
) -> dict:
    from sqlalchemy import text as sa_text
    unsubscribed = bool(body.get("unsubscribed", False))
    await session.execute(
        sa_text("UPDATE users SET broadcast_unsubscribed = :val WHERE id = :uid AND tenant_id = :tid"),
        {"val": unsubscribed, "uid": user.id, "tid": user.tenant_id},
    )
    await session.commit()
    return {"broadcast_unsubscribed": unsubscribed}


@router.get(
    "/me/broadcast-subscription",
    summary="Get broadcast email subscription status",
)
async def get_broadcast_subscription(
    user: VerifiedUserDep,
) -> dict:
    return {"broadcast_unsubscribed": user.broadcast_unsubscribed}


@router.post(
    "/confirm-deletion",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Confirm account deletion using the token from the confirmation email",
)
async def confirm_deletion(
    req: ConfirmDeletionRequest,
    uow: UoWDep,
    token_store: TokenStoreDep,
    hasher: HasherDep,
) -> None:
    svc = UserService(uow=uow, token_store=token_store, hasher=hasher)
    await svc.confirm_deletion(req.token)

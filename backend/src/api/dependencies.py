"""Compatibility module: re-exports deps.py symbols + service factory functions."""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, SessionDep  # noqa: F401 — re-exported
from src.application.media.service import MediaApplicationService
from src.application.search.service import SearchService
from src.config import get_settings
from src.infrastructure.database.session import get_db_session  # noqa: F401 — re-exported
from src.infrastructure.media.s3 import S3Service
from src.infrastructure.repositories.media import MediaRepository
from src.infrastructure.search.repository import SearchRepository


def get_media_service(session: SessionDep) -> MediaApplicationService:
    settings = get_settings()
    repo = MediaRepository(session)
    s3 = S3Service(
        bucket=settings.s3_bucket,
        region=settings.aws_region,
        access_key_id=settings.aws_access_key_id or None,
        secret_access_key=settings.aws_secret_access_key or None,
        endpoint_url=settings.s3_endpoint_url or None,
        public_url=settings.s3_public_url or None,
    )
    return MediaApplicationService(repo=repo, s3=s3)


def get_search_service(session: SessionDep) -> SearchService:
    repo = SearchRepository(session)
    return SearchService(repo=repo)

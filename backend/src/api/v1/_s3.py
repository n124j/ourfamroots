"""Shared S3 / presigned-URL helpers used by multiple API modules."""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse


def _make_s3_client(settings):
    """S3 client for API operations (upload, delete). Uses the internal endpoint URL."""
    import boto3
    from botocore.config import Config as BotoCfg

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.aws_access_key_id or "minioadmin",
        aws_secret_access_key=settings.aws_secret_access_key or "minioadmin",
        region_name=settings.aws_region,
        config=BotoCfg(signature_version="s3v4"),
    )


def _parse_s3_public_origin(settings) -> tuple[Optional[str], str]:
    """Extract the origin (scheme+host) and path prefix from S3_PUBLIC_URL.

    When S3_PUBLIC_URL is e.g. ``https://domain.com/s3``, boto3 must use only
    the origin (``https://domain.com``) as its endpoint so the presigned URL
    signature is computed without the ``/s3`` path prefix.  The path prefix is
    injected back into the URL *after* signing — nginx strips it before
    forwarding to MinIO, so the signed path (``/{bucket}/{key}``) matches what
    MinIO actually receives.

    Returns (origin_or_None, path_prefix_string).
    """
    raw = (settings.s3_public_url or settings.s3_endpoint_url or "").rstrip("/")
    if not raw:
        return None, ""
    parsed = urlparse(raw)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path_prefix = parsed.path.rstrip("/")
    return origin, path_prefix


def _make_presign_client(settings):
    """S3 client used only for generating presigned GET URLs.

    Uses the *origin* of S3_PUBLIC_URL (scheme + host, no path) so the
    presigned signature uses the browser-visible hostname.  Any path prefix
    (e.g. ``/s3``) is stripped here and re-added after signing in
    ``presign_photo``.
    """
    import boto3
    from botocore.config import Config as BotoCfg

    origin, _ = _parse_s3_public_origin(settings)

    return boto3.client(
        "s3",
        endpoint_url=origin,
        aws_access_key_id=settings.aws_access_key_id or "minioadmin",
        aws_secret_access_key=settings.aws_secret_access_key or "minioadmin",
        region_name=settings.aws_region,
        config=BotoCfg(signature_version="s3v4"),
    )


def presign_photo(photo_url: Optional[str], expires_in: int = 3600) -> Optional[str]:
    """Return a browser-accessible URL for a person photo.

    Handles three storage formats:
    - None / empty          → None
    - preset:N              → returned as-is (data URI resolved client-side)
    - bare S3 key           → presigned GET URL using the public endpoint
    - legacy full URL       → key extracted, then presigned GET URL
    """
    if not photo_url or photo_url.startswith("preset:"):
        return photo_url

    from src.config import get_settings
    settings = get_settings()
    bucket = settings.s3_bucket or "ourfamroots-local"

    # Extract key from legacy full-URL storage format (either endpoint variant)
    for base in filter(None, [
        (settings.s3_public_url or "").rstrip("/"),
        (settings.s3_endpoint_url or "").rstrip("/"),
    ]):
        prefix = f"{base}/{bucket}/"
        if photo_url.startswith(prefix):
            photo_url = photo_url[len(prefix):]
            break
    else:
        if photo_url.startswith("/"):
            stripped = photo_url.lstrip("/")
            photo_url = stripped[len(bucket) + 1:] if stripped.startswith(f"{bucket}/") else stripped
        # else: already a bare key — leave as-is

    s3 = _make_presign_client(settings)
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": photo_url},
        ExpiresIn=expires_in,
    )

    # Re-inject the path prefix (e.g. /s3) that was stripped from the endpoint.
    # The signature was computed without it so nginx can strip it and the signed
    # path still matches what MinIO receives.
    origin, path_prefix = _parse_s3_public_origin(settings)
    if origin and path_prefix:
        url = url.replace(origin + "/", origin + path_prefix + "/", 1)

    return url

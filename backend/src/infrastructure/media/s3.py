"""S3 storage client — presigned URLs, upload, download, delete."""
from __future__ import annotations

import uuid
from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from src.domain.media.exceptions import StorageError


# ── Key conventions ────────────────────────────────────────────────────────────

def make_storage_key(
    tenant_id: uuid.UUID,
    tree_id: uuid.UUID,
    media_id: uuid.UUID,
    filename: str,
    person_id: Optional[uuid.UUID] = None,
) -> str:
    """
    Build an S3 object key.

    Pattern:
      {tenant}/{tree}/persons/{person}/{media_id}/original.{ext}
      {tenant}/{tree}/tree/{media_id}/original.{ext}
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    scope = f"persons/{person_id}" if person_id else "tree"
    return f"{tenant_id}/{tree_id}/{scope}/{media_id}/original.{ext}"


def make_variant_key(original_key: str, variant: str) -> str:
    """
    Derive a variant key from the original key.

    original: {prefix}/original.jpg
    variants: {prefix}/thumb_200.webp, {prefix}/compressed.webp, etc.
    """
    prefix = original_key.rsplit("/original.", 1)[0]
    return f"{prefix}/{variant}.webp"


def make_preview_key(original_key: str) -> str:
    prefix = original_key.rsplit("/original.", 1)[0]
    return f"{prefix}/preview.jpg"


def make_metadata_key(original_key: str) -> str:
    prefix = original_key.rsplit("/original.", 1)[0]
    return f"{prefix}/metadata.json"


# ── S3 Service ─────────────────────────────────────────────────────────────────

class S3Service:
    """Thin wrapper around boto3 S3 client with typed helpers."""

    def __init__(
        self,
        bucket: str,
        region: str,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,  # for LocalStack / MinIO (server-side)
        public_url: Optional[str] = None,    # browser-accessible base URL (replaces endpoint_url in presigned URLs)
    ) -> None:
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url.rstrip("/") if endpoint_url else None
        self._public_url = public_url.rstrip("/") if public_url else None

        # Parse public URL into origin (scheme+host) and path prefix.
        # When public_url is e.g. "https://domain.com/s3", the presign client
        # must use only "https://domain.com" as its endpoint so the S3v4
        # signature path doesn't include "/s3".  The path prefix is injected
        # back into the URL after signing.
        if self._public_url:
            parsed = urlparse(self._public_url)
            self._public_origin = f"{parsed.scheme}://{parsed.netloc}"
            self._public_path_prefix = parsed.path.rstrip("/")
        else:
            self._public_origin = None
            self._public_path_prefix = ""

        _cfg = Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

        session = boto3.session.Session()
        self._client = session.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint_url,
            config=_cfg,
        )

        # Separate client for presigned URLs — uses the public origin so the
        # signed Host header matches what the browser sends.
        presign_endpoint = self._public_origin or endpoint_url
        if presign_endpoint != endpoint_url:
            self._presign_client = session.client(
                "s3",
                region_name=region,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                endpoint_url=presign_endpoint,
                config=_cfg,
            )
        else:
            self._presign_client = self._client

    # ── Presigned URLs ─────────────────────────────────────────────────────────

    def _inject_path_prefix(self, url: str) -> str:
        """Re-insert the public URL's path prefix (e.g. ``/s3``) after signing."""
        if self._public_origin and self._public_path_prefix:
            url = url.replace(
                self._public_origin + "/",
                self._public_origin + self._public_path_prefix + "/",
                1,
            )
        return url

    def presigned_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in: int = 3600,
        max_size_bytes: int = 50 * 1024 * 1024,
    ) -> str:
        """
        Generate a presigned PUT URL for direct browser-to-S3 upload.
        The client must set Content-Type to match *content_type*.
        """
        try:
            url = self._presign_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
                HttpMethod="PUT",
            )
            return self._inject_path_prefix(url)
        except ClientError as exc:
            raise StorageError("presign_upload", str(exc)) from exc

    def presigned_post(
        self,
        key: str,
        content_type: str,
        expires_in: int = 3600,
        max_size_bytes: int = 50 * 1024 * 1024,
    ) -> dict:
        """
        Generate a presigned POST form (enforces size + content-type conditions).
        Preferred over presigned PUT for browser uploads — allows server-side
        Content-Length-Range enforcement.
        Returns { url, fields } suitable for multipart/form-data.
        """
        try:
            result = self._presign_client.generate_presigned_post(
                Bucket=self._bucket,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, max_size_bytes],
                ],
                ExpiresIn=expires_in,
            )
            result["url"] = self._inject_path_prefix(result["url"])
            return result
        except ClientError as exc:
            raise StorageError("presign_post", str(exc)) from exc

    def presigned_download_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: Optional[str] = None,
    ) -> str:
        """Generate a presigned GET URL for temporary download access."""
        params: dict = {"Bucket": self._bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{filename}"'
            )
        try:
            url = self._presign_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in,
            )
            return self._inject_path_prefix(url)
        except ClientError as exc:
            raise StorageError("presign_download", str(exc)) from exc

    # ── Object operations ──────────────────────────────────────────────────────

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Optional[dict[str, str]] = None,
    ) -> None:
        """Upload raw bytes to S3 (used by Celery workers for variants)."""
        extra: dict = {"ContentType": content_type}
        if metadata:
            extra["Metadata"] = metadata
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                **extra,
            )
        except ClientError as exc:
            raise StorageError("upload_bytes", str(exc)) from exc

    def download_bytes(self, key: str) -> bytes:
        """Download an object to memory (used by Celery workers)."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            raise StorageError("download_bytes", str(exc)) from exc

    def delete_object(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            raise StorageError("delete_object", str(exc)) from exc

    def delete_prefix(self, prefix: str) -> int:
        """Delete all objects under a key prefix. Returns count deleted."""
        paginator = self._client.get_paginator("list_objects_v2")
        deleted = 0
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if not objects:
                continue
            self._client.delete_objects(
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
            )
            deleted += len(objects)
        return deleted

    def object_exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                return False
            raise StorageError("head_object", str(exc)) from exc

    def get_object_size(self, key: str) -> int:
        """Return the stored size of an object in bytes."""
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
            return response["ContentLength"]
        except ClientError as exc:
            raise StorageError("head_object_size", str(exc)) from exc

    # ── Public URL (CloudFront / public bucket) ────────────────────────────────

    def public_url(self, key: str, cdn_base: Optional[str] = None) -> str:
        """
        Return the public URL for a key.
        Use *cdn_base* (CloudFront distribution URL) in production.
        Falls back to S3 regional URL.
        """
        if cdn_base:
            return f"{cdn_base.rstrip('/')}/{key}"
        return (
            f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"
        )


# ── Dependency factory (called once at app startup) ────────────────────────────

_s3_service: Optional[S3Service] = None


def init_s3(
    bucket: str,
    region: str,
    access_key_id: Optional[str] = None,
    secret_access_key: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    public_url: Optional[str] = None,
) -> S3Service:
    global _s3_service
    _s3_service = S3Service(
        bucket=bucket,
        region=region,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        endpoint_url=endpoint_url,
        public_url=public_url,
    )
    return _s3_service


def get_s3() -> S3Service:
    if _s3_service is None:
        raise RuntimeError("S3Service not initialised. Call init_s3() on startup.")
    return _s3_service

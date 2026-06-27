"""Media-specific domain exceptions."""
from __future__ import annotations

import uuid
from src.domain.exceptions import DomainError, ValidationError


class UnsupportedMediaTypeError(ValidationError):
    def __init__(self, content_type: str) -> None:
        super().__init__(
            message=f"File type '{content_type}' is not supported.",
            field="content_type",
        )
        self.code = "UNSUPPORTED_MEDIA_TYPE"
        self.content_type = content_type


class FileTooLargeError(ValidationError):
    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        mb = max_bytes // (1024 * 1024)
        super().__init__(
            message=f"File size {size_bytes:,} bytes exceeds the {mb} MB limit.",
            field="file_size",
        )
        self.code = "FILE_TOO_LARGE"
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes


class MediaNotFoundError(DomainError):
    def __init__(self, media_id: uuid.UUID) -> None:
        super().__init__(
            message=f"Media item {media_id} not found.",
            code="MEDIA_NOT_FOUND",
        )
        self.media_id = media_id


class MediaNotReadyError(DomainError):
    def __init__(self, media_id: uuid.UUID, status: str) -> None:
        super().__init__(
            message=f"Media {media_id} is not yet ready (status: {status}).",
            code="MEDIA_NOT_READY",
        )
        self.media_id = media_id
        self.status = status


class MediaProcessingError(DomainError):
    def __init__(self, media_id: uuid.UUID, detail: str) -> None:
        super().__init__(
            message=f"Media processing failed for {media_id}: {detail}",
            code="MEDIA_PROCESSING_FAILED",
        )
        self.media_id = media_id
        self.detail = detail


class StorageError(DomainError):
    def __init__(self, operation: str, detail: str) -> None:
        super().__init__(
            message=f"Storage operation '{operation}' failed: {detail}",
            code="STORAGE_ERROR",
        )
        self.operation = operation

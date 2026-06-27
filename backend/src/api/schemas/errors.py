"""RFC 7807 Problem Details schema.

All error responses follow this shape:

    {
        "type":     "https://ourfamroots.app/errors/not-found",
        "title":    "Resource Not Found",
        "status":   404,
        "detail":   "User 'abc-123' was not found.",
        "instance": "/api/v1/users/abc-123",
        "errors":   []          // only for validation errors
    }
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FieldError(BaseModel):
    field: str
    message: str
    code: str | None = None


class ProblemDetail(BaseModel):
    type: str = Field(description="A URI that identifies the problem type")
    title: str = Field(description="Short human-readable summary")
    status: int = Field(description="HTTP status code")
    detail: str = Field(description="Human-readable explanation specific to this occurrence")
    instance: str | None = Field(default=None, description="URI of the specific request")
    errors: list[FieldError] = Field(default_factory=list, description="Field-level validation errors")

    model_config = {"json_schema_extra": {"example": {
        "type": "https://ourfamroots.app/errors/not-found",
        "title": "Resource Not Found",
        "status": 404,
        "detail": "User '3fa85f64-...' was not found.",
        "instance": "/api/v1/users/me",
        "errors": [],
    }}}

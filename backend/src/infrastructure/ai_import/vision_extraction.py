"""Calls Claude (vision + forced tool use) to extract a family tree draft from
a screenshot: people (with an optional normalized photo bounding box) and
family groups (unions + parent/child links). Never writes to real tree tables
— this module only returns a validated draft."""
from __future__ import annotations

import base64
from typing import Optional

from anthropic import Anthropic
from pydantic import BaseModel, field_validator


class VisionExtractionError(Exception):
    """Raised when the vision API call fails or returns an unusable response."""


class ExtractedPerson(BaseModel):
    id: str
    display_given_name: str = ""
    display_surname: str = ""
    sex: str = "UNKNOWN"
    bbox: Optional[list[float]] = None

    @field_validator("bbox")
    @classmethod
    def _validate_bbox(cls, v: Optional[list[float]]) -> Optional[list[float]]:
        if v is None:
            return None
        if len(v) != 4 or any((not isinstance(n, (int, float))) or n < 0 or n > 1 for n in v):
            return None  # drop a malformed box rather than fail the whole extraction
        return [float(n) for n in v]

    @field_validator("sex")
    @classmethod
    def _validate_sex(cls, v: str) -> str:
        return v if v in ("MALE", "FEMALE", "OTHER", "UNKNOWN") else "UNKNOWN"


class ExtractedFamilyGroup(BaseModel):
    id: str
    union_type: str = "UNKNOWN"
    parent_ids: list[str] = []
    children: dict[str, str] = {}

    @field_validator("union_type")
    @classmethod
    def _validate_union_type(cls, v: str) -> str:
        return v if v in ("MARRIAGE", "PARTNERSHIP", "COHABITATION", "UNKNOWN") else "UNKNOWN"


class ExtractedTreeDraft(BaseModel):
    persons: list[ExtractedPerson] = []
    family_groups: list[ExtractedFamilyGroup] = []


_EXTRACTION_TOOL = {
    "name": "record_family_tree",
    "description": (
        "Record every person and family relationship visible in the family "
        "tree chart image. Omit any person or relationship you are not "
        "reasonably confident about rather than guessing."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "persons": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "A short unique slug for this person, e.g. 'john_smith'."},
                        "display_given_name": {"type": "string"},
                        "display_surname": {"type": "string"},
                        "sex": {"type": "string", "enum": ["MALE", "FEMALE", "OTHER", "UNKNOWN"]},
                        "bbox": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 4,
                            "maxItems": 4,
                            "description": "Normalized [x, y, width, height] (each 0-1) bounding box of this person's photo. Omit entirely if no photo is shown for them.",
                        },
                    },
                    "required": ["id", "display_given_name", "display_surname", "sex"],
                },
            },
            "family_groups": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "union_type": {"type": "string", "enum": ["MARRIAGE", "PARTNERSHIP", "COHABITATION", "UNKNOWN"]},
                        "parent_ids": {"type": "array", "items": {"type": "string"}},
                        "children": {
                            "type": "object",
                            "description": "Map of child person id -> parentage type.",
                            "additionalProperties": {
                                "type": "string",
                                "enum": ["BIOLOGICAL", "ADOPTIVE", "STEP", "FOSTER", "UNKNOWN"],
                            },
                        },
                    },
                    "required": ["id", "parent_ids", "children"],
                },
            },
        },
        "required": ["persons", "family_groups"],
    },
}

_PROMPT = (
    "This image is a family tree chart. Identify every person shown (by the "
    "label near their photo or box) and every parent-child / spousal "
    "relationship the chart's lines indicate. Call record_family_tree with "
    "the full result."
)


def extract_tree_from_image(
    image_bytes: bytes,
    media_type: str,
    api_key: str,
    model: str,
) -> ExtractedTreeDraft:
    """Call Claude vision with forced tool use and return a validated draft.

    Raises VisionExtractionError on any API failure, missing tool_use block,
    or a response that fails ExtractedTreeDraft validation.
    """
    client = Anthropic(api_key=api_key)
    encoded = base64.standard_b64encode(image_bytes).decode("ascii")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            tools=[_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "record_family_tree"},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}},
                    {"type": "text", "text": _PROMPT},
                ],
            }],
        )
    except Exception as exc:
        raise VisionExtractionError(f"Vision API call failed: {exc}") from exc

    tool_block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    if tool_block is None:
        raise VisionExtractionError("Vision API response did not include a tool_use block")

    try:
        return ExtractedTreeDraft(**tool_block.input)
    except Exception as exc:
        raise VisionExtractionError(f"Vision API response failed schema validation: {exc}") from exc

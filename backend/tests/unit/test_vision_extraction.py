"""Unit tests for vision_extraction: parsing/validating Claude's tool-use output."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.ai_import.vision_extraction import (
    ExtractedTreeDraft,
    VisionExtractionError,
    extract_tree_from_image,
)


def _fake_anthropic_response(tool_input: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.input = tool_input
    resp = MagicMock()
    resp.content = [block]
    return resp


@patch("src.infrastructure.ai_import.vision_extraction.Anthropic")
def test_extract_tree_from_image_parses_valid_response(mock_anthropic_cls) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _fake_anthropic_response({
        "persons": [
            {"id": "jane", "display_given_name": "Jane", "display_surname": "Doe",
             "sex": "FEMALE", "bbox": [0.1, 0.1, 0.2, 0.2]},
            {"id": "no_photo_kid", "display_given_name": "Sam", "display_surname": "Doe",
             "sex": "UNKNOWN"},
        ],
        "family_groups": [
            {"id": "fg1", "union_type": "MARRIAGE", "parent_ids": ["jane"],
             "children": {"no_photo_kid": "BIOLOGICAL"}},
        ],
    })

    draft = extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")

    assert isinstance(draft, ExtractedTreeDraft)
    assert len(draft.persons) == 2
    assert draft.persons[0].bbox == [0.1, 0.1, 0.2, 0.2]
    assert draft.persons[1].bbox is None
    assert draft.family_groups[0].children == {"no_photo_kid": "BIOLOGICAL"}


@patch("src.infrastructure.ai_import.vision_extraction.Anthropic")
def test_extract_tree_from_image_drops_malformed_bbox(mock_anthropic_cls) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _fake_anthropic_response({
        "persons": [
            {"id": "p1", "display_given_name": "A", "display_surname": "B",
             "sex": "MALE", "bbox": [1.5, 0, 0, 0]},  # out of [0,1] range
        ],
        "family_groups": [],
    })

    draft = extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")
    assert draft.persons[0].bbox is None


@patch("src.infrastructure.ai_import.vision_extraction.Anthropic")
def test_extract_tree_from_image_raises_on_no_tool_use_block(mock_anthropic_cls) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    text_block = MagicMock()
    text_block.type = "text"
    resp = MagicMock()
    resp.content = [text_block]
    mock_client.messages.create.return_value = resp

    with pytest.raises(VisionExtractionError):
        extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")


@patch("src.infrastructure.ai_import.vision_extraction.Anthropic")
def test_extract_tree_from_image_wraps_api_errors(mock_anthropic_cls) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = RuntimeError("network down")

    with pytest.raises(VisionExtractionError):
        extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")

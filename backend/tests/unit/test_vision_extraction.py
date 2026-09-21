"""Unit tests for vision_extraction: parsing/validating Claude's tool-use output."""
from __future__ import annotations

import json
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
def test_extract_tree_from_image_rejects_family_groups_referencing_unknown_persons(mock_anthropic_cls) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _fake_anthropic_response({
        "persons": [],
        "family_groups": [
            {"id": "fg1", "union_type": "MARRIAGE", "parent_ids": ["salim_khan", "helen"],
             "children": {}},
        ],
    })

    with pytest.raises(VisionExtractionError):
        extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")


@patch("src.infrastructure.ai_import.vision_extraction.Anthropic")
def test_extract_tree_from_image_retries_after_malformed_first_response(mock_anthropic_cls) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    malformed = _fake_anthropic_response({
        "persons": [{"id": "jane", "display_given_name": "Jane", "display_surname": "Doe", "sex": "FEMALE"}],
        "family_groups": "not-a-list",  # garbled tool call, as seen in production
    })
    valid = _fake_anthropic_response({
        "persons": [{"id": "jane", "display_given_name": "Jane", "display_surname": "Doe", "sex": "FEMALE"}],
        "family_groups": [],
    })
    mock_client.messages.create.side_effect = [malformed, valid]

    draft = extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")

    assert len(draft.persons) == 1
    assert mock_client.messages.create.call_count == 2


@patch("src.infrastructure.ai_import.vision_extraction.Anthropic")
def test_extract_tree_from_image_gives_up_after_max_attempts(mock_anthropic_cls) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _fake_anthropic_response({
        "persons": [],
        "family_groups": "not-a-list",
    })

    with pytest.raises(VisionExtractionError):
        extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")
    assert mock_client.messages.create.call_count == 2


@patch("src.infrastructure.ai_import.vision_extraction.Anthropic")
def test_extract_tree_from_image_repairs_family_groups_as_duplicated_json_string(mock_anthropic_cls) -> None:
    # Reproduces the exact glitch seen in production: family_groups arrives
    # as a JSON-encoded string holding a duplicate of the whole {persons,
    # family_groups} object, instead of an actual list.
    real_persons = [
        {"id": "salim_khan", "display_given_name": "Salim", "display_surname": "Khan", "sex": "MALE"},
        {"id": "helen", "display_given_name": "Helen", "display_surname": "Khan", "sex": "FEMALE"},
    ]
    real_family_groups = [
        {"id": "fg1", "union_type": "MARRIAGE", "parent_ids": ["salim_khan", "helen"], "children": {}},
    ]
    duplicated_blob = json.dumps({"persons": real_persons, "family_groups": real_family_groups})

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _fake_anthropic_response({
        "persons": real_persons,
        "family_groups": duplicated_blob,
    })

    draft = extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")

    assert len(draft.persons) == 2
    assert len(draft.family_groups) == 1
    assert draft.family_groups[0].parent_ids == ["salim_khan", "helen"]
    assert mock_client.messages.create.call_count == 1  # repaired on the first attempt, no retry needed


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

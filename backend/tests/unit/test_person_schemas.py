"""Unit tests for person-related Pydantic schemas.

Covers changes introduced in:
  - CreatePersonRequest.is_deceased field (deceased status on creation)
  - MergeTreesRequest / MergeSource validation
"""
from __future__ import annotations

import uuid
import pytest
from pydantic import ValidationError

from src.application.genealogy.schemas import CreatePersonRequest, UpdatePersonRequest


# ── CreatePersonRequest ────────────────────────────────────────────────────────

class TestCreatePersonRequest:
    def test_defaults_to_living(self):
        req = CreatePersonRequest()
        assert req.is_living is True
        assert req.is_deceased is False

    def test_deceased_flag_accepted(self):
        req = CreatePersonRequest(is_living=False, is_deceased=True)
        assert req.is_living is False
        assert req.is_deceased is True

    def test_living_and_deceased_both_false_yields_unknown(self):
        req = CreatePersonRequest(is_living=False, is_deceased=False)
        assert req.is_living is False
        assert req.is_deceased is False

    def test_given_name_max_length(self):
        with pytest.raises(ValidationError):
            CreatePersonRequest(given_name="A" * 201)

    def test_surname_max_length(self):
        with pytest.raises(ValidationError):
            CreatePersonRequest(surname="B" * 201)

    def test_invalid_sex_rejected(self):
        with pytest.raises(ValidationError):
            CreatePersonRequest(sex="ALIEN")  # type: ignore[arg-type]

    def test_valid_sex_values(self):
        for sex in ("MALE", "FEMALE", "OTHER", "UNKNOWN"):
            req = CreatePersonRequest(sex=sex)  # type: ignore[arg-type]
            assert req.sex.value == sex


# ── UpdatePersonRequest ────────────────────────────────────────────────────────

class TestUpdatePersonRequest:
    def test_has_is_deceased_field(self):
        req = UpdatePersonRequest(is_living=False, is_deceased=True)
        assert req.is_deceased is True

    def test_defaults(self):
        req = UpdatePersonRequest()
        assert req.is_living is True
        assert req.is_deceased is False


# ── MergeTreesRequest (API layer schema) ──────────────────────────────────────

class TestMergeTreesSchema:
    """Validate the MergeTreesRequest Pydantic model used by POST /trees/merge."""

    def _import(self):
        from src.api.v1.collaboration import MergeTreesRequest, MergeSource
        return MergeTreesRequest, MergeSource

    def test_requires_at_least_two_sources(self):
        MergeTreesRequest, MergeSource = self._import()
        with pytest.raises(ValidationError):
            MergeTreesRequest(
                new_tree_name="Test",
                sources=[MergeSource(tree_id=uuid.uuid4(), pivot_person_id=uuid.uuid4())],
            )

    def test_valid_with_two_sources(self):
        MergeTreesRequest, MergeSource = self._import()
        req = MergeTreesRequest(
            new_tree_name="Merged",
            sources=[
                MergeSource(tree_id=uuid.uuid4(), pivot_person_id=uuid.uuid4()),
                MergeSource(tree_id=uuid.uuid4(), pivot_person_id=uuid.uuid4()),
            ],
        )
        assert req.new_tree_name == "Merged"
        assert len(req.sources) == 2

    def test_description_optional(self):
        MergeTreesRequest, MergeSource = self._import()
        req = MergeTreesRequest(
            new_tree_name="No Desc",
            sources=[
                MergeSource(tree_id=uuid.uuid4(), pivot_person_id=uuid.uuid4()),
                MergeSource(tree_id=uuid.uuid4(), pivot_person_id=uuid.uuid4()),
            ],
        )
        assert req.new_tree_description is None

    def test_name_cannot_be_empty(self):
        MergeTreesRequest, MergeSource = self._import()
        with pytest.raises(ValidationError):
            MergeTreesRequest(
                new_tree_name="",
                sources=[
                    MergeSource(tree_id=uuid.uuid4(), pivot_person_id=uuid.uuid4()),
                    MergeSource(tree_id=uuid.uuid4(), pivot_person_id=uuid.uuid4()),
                ],
            )

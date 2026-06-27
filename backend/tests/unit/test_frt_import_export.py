"""Unit tests for .frt import/export schema validation.

Verifies that the _FrtPerson and _FrtFamilyGroup Pydantic models correctly
parse all fields — including the 'more details' fields (life dates, social
handles, custom_label) that were added in the export/import round-trip fix.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from src.api.v1.collaboration import _FrtPerson, _FrtFamilyGroup, ImportTreeRequest


# ── _FrtPerson ───────────────────────────────────────────────────

class TestFrtPerson:
    def test_minimal_person(self) -> None:
        p = _FrtPerson(id="abc-123")
        assert p.id == "abc-123"
        assert p.display_given_name == ""
        assert p.display_surname == ""
        assert p.sex == "UNKNOWN"
        assert p.is_living is True
        assert p.is_deceased is False
        assert p.photo_url is None
        assert p.birth_date is None
        assert p.death_date is None
        assert p.birth_year is None
        assert p.death_year is None
        assert p.facebook_handle is None
        assert p.x_handle is None
        assert p.linkedin_handle is None

    def test_full_person_with_all_fields(self) -> None:
        p = _FrtPerson(
            id="p1",
            display_given_name="Mary Anne",
            display_surname="Trump",
            sex="FEMALE",
            is_living=False,
            is_deceased=True,
            photo_url="https://example.com/photo.jpg",
            birth_date="1912-05-10",
            death_date="2000-08-07",
            birth_year=1912,
            death_year=2000,
            facebook_handle="maryanne",
            x_handle="maryanne_t",
            linkedin_handle="in/maryanne",
        )
        assert p.display_given_name == "Mary Anne"
        assert p.display_surname == "Trump"
        assert p.sex == "FEMALE"
        assert p.is_living is False
        assert p.is_deceased is True
        assert p.photo_url == "https://example.com/photo.jpg"
        assert p.birth_date == "1912-05-10"
        assert p.death_date == "2000-08-07"
        assert p.birth_year == 1912
        assert p.death_year == 2000
        assert p.facebook_handle == "maryanne"
        assert p.x_handle == "maryanne_t"
        assert p.linkedin_handle == "in/maryanne"

    def test_year_only_fields(self) -> None:
        p = _FrtPerson(id="p2", birth_year=1850, death_year=1920)
        assert p.birth_year == 1850
        assert p.death_year == 1920
        assert p.birth_date is None
        assert p.death_date is None

    def test_date_only_fields(self) -> None:
        p = _FrtPerson(id="p3", birth_date="1990-01-15", death_date="2060-12-31")
        assert p.birth_date == "1990-01-15"
        assert p.death_date == "2060-12-31"
        assert p.birth_year is None
        assert p.death_year is None

    def test_social_handles_only(self) -> None:
        p = _FrtPerson(
            id="p4",
            facebook_handle="john.doe",
            x_handle="johndoe",
            linkedin_handle="in/johndoe",
        )
        assert p.facebook_handle == "john.doe"
        assert p.x_handle == "johndoe"
        assert p.linkedin_handle == "in/johndoe"

    def test_missing_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            _FrtPerson()  # type: ignore[call-arg]


# ── _FrtFamilyGroup ──────────────────────────────────────────────

class TestFrtFamilyGroup:
    def test_minimal_family_group(self) -> None:
        fg = _FrtFamilyGroup(id="fg1")
        assert fg.id == "fg1"
        assert fg.union_type == "UNKNOWN"
        assert fg.custom_label is None
        assert fg.parent_ids == []
        assert fg.children == {}

    def test_full_family_group(self) -> None:
        fg = _FrtFamilyGroup(
            id="fg1",
            union_type="MARRIAGE",
            custom_label="Church Wedding",
            parent_ids=["p1", "p2"],
            children={"p3": "BIOLOGICAL", "p4": "ADOPTIVE"},
        )
        assert fg.union_type == "MARRIAGE"
        assert fg.custom_label == "Church Wedding"
        assert fg.parent_ids == ["p1", "p2"]
        assert fg.children == {"p3": "BIOLOGICAL", "p4": "ADOPTIVE"}

    def test_custom_label_none_by_default(self) -> None:
        fg = _FrtFamilyGroup(id="fg2", union_type="PARTNERSHIP")
        assert fg.custom_label is None

    def test_missing_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            _FrtFamilyGroup()  # type: ignore[call-arg]


# ── ImportTreeRequest (full round-trip payload) ──────────────────

class TestImportTreeRequest:
    def test_full_payload_parses(self) -> None:
        payload = {
            "frt_version": "1.0",
            "tree_name": "Smith Family",
            "tree_description": "A test family",
            "persons": [
                {
                    "id": "p1",
                    "display_given_name": "John",
                    "display_surname": "Smith",
                    "sex": "MALE",
                    "is_living": False,
                    "is_deceased": True,
                    "birth_date": "1920-03-15",
                    "death_date": "1995-11-20",
                    "birth_year": 1920,
                    "death_year": 1995,
                    "facebook_handle": "john.smith",
                    "x_handle": "jsmith",
                    "linkedin_handle": "in/johnsmith",
                },
                {
                    "id": "p2",
                    "display_given_name": "Jane",
                    "display_surname": "Smith",
                    "sex": "FEMALE",
                    "is_living": True,
                    "is_deceased": False,
                },
            ],
            "family_groups": [
                {
                    "id": "fg1",
                    "union_type": "MARRIAGE",
                    "custom_label": "First Marriage",
                    "parent_ids": ["p1", "p2"],
                    "children": {"p3": "BIOLOGICAL"},
                },
            ],
        }
        req = ImportTreeRequest(**payload)
        assert req.tree_name == "Smith Family"
        assert len(req.persons) == 2

        p1 = req.persons[0]
        assert p1.birth_date == "1920-03-15"
        assert p1.death_date == "1995-11-20"
        assert p1.birth_year == 1920
        assert p1.death_year == 1995
        assert p1.facebook_handle == "john.smith"
        assert p1.x_handle == "jsmith"
        assert p1.linkedin_handle == "in/johnsmith"

        p2 = req.persons[1]
        assert p2.birth_date is None
        assert p2.facebook_handle is None

        fg = req.family_groups[0]
        assert fg.custom_label == "First Marriage"

    def test_backward_compatible_with_old_frt(self) -> None:
        """Old .frt files without the new fields should still import fine."""
        payload = {
            "frt_version": "1.0",
            "tree_name": "Old Tree",
            "persons": [
                {
                    "id": "p1",
                    "display_given_name": "Alice",
                    "display_surname": "Jones",
                    "sex": "FEMALE",
                    "is_living": True,
                    "is_deceased": False,
                },
            ],
            "family_groups": [
                {
                    "id": "fg1",
                    "union_type": "UNKNOWN",
                    "parent_ids": [],
                    "children": {},
                },
            ],
        }
        req = ImportTreeRequest(**payload)
        assert req.persons[0].birth_date is None
        assert req.persons[0].birth_year is None
        assert req.persons[0].facebook_handle is None
        assert req.family_groups[0].custom_label is None

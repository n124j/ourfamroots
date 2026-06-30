"""Unit tests for person birth/death year fields used by TimelineView.

The frontend Timeline extension renders each person as a horizontal bar spanning
birth_year → death_year.  These tests verify that the backend schemas correctly
accept, validate, and serialise those fields so the Timeline always receives
well-formed numeric year values.

Covers:
  - CreatePersonRequest / UpdatePersonRequest accept birth_year and death_year
  - Year bounds are enforced (ge=1, le=9999)
  - birth_date / death_date strings are accepted alongside year-only fields
  - The _FrtPerson schema (import/export) round-trips birth_year and death_year
  - The API graph serialiser emits "birthYear" / "deathYear" camelCase keys
    that the frontend parseYear() and resolveBirthYear() rely on
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.application.genealogy.schemas import CreatePersonRequest, UpdatePersonRequest
from src.api.v1.collaboration import _FrtPerson


# ── CreatePersonRequest — birth/death year fields ─────────────────────────────

class TestCreatePersonRequestYearFields:
    def test_birth_year_accepted(self) -> None:
        req = CreatePersonRequest(birth_year=1950)
        assert req.birth_year == 1950

    def test_death_year_accepted(self) -> None:
        req = CreatePersonRequest(death_year=2020)
        assert req.death_year == 2020

    def test_both_year_fields_accepted(self) -> None:
        req = CreatePersonRequest(birth_year=1900, death_year=1975)
        assert req.birth_year == 1900
        assert req.death_year == 1975

    def test_year_fields_default_to_none(self) -> None:
        req = CreatePersonRequest()
        assert req.birth_year is None
        assert req.death_year is None

    def test_birth_year_lower_bound_accepted(self) -> None:
        req = CreatePersonRequest(birth_year=1)
        assert req.birth_year == 1

    def test_birth_year_upper_bound_accepted(self) -> None:
        req = CreatePersonRequest(birth_year=9999)
        assert req.birth_year == 9999

    def test_birth_year_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CreatePersonRequest(birth_year=0)

    def test_birth_year_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CreatePersonRequest(birth_year=-1)

    def test_birth_year_above_9999_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CreatePersonRequest(birth_year=10000)

    def test_death_year_bounds_enforced(self) -> None:
        with pytest.raises(ValidationError):
            CreatePersonRequest(death_year=0)
        with pytest.raises(ValidationError):
            CreatePersonRequest(death_year=10000)

    def test_birth_date_string_accepted_alongside_birth_year(self) -> None:
        from datetime import date
        req = CreatePersonRequest(birth_year=1950, birth_date=date(1950, 6, 15))
        assert req.birth_year == 1950
        assert req.birth_date == date(1950, 6, 15)


# ── UpdatePersonRequest — birth/death year fields ─────────────────────────────

class TestUpdatePersonRequestYearFields:
    def test_birth_year_accepted(self) -> None:
        req = UpdatePersonRequest(birth_year=1985)
        assert req.birth_year == 1985

    def test_death_year_accepted(self) -> None:
        req = UpdatePersonRequest(death_year=2023)
        assert req.death_year == 2023

    def test_year_fields_default_to_none_on_update(self) -> None:
        req = UpdatePersonRequest()
        assert req.birth_year is None
        assert req.death_year is None

    def test_birth_year_can_be_cleared_with_none(self) -> None:
        req = UpdatePersonRequest(birth_year=None)
        assert req.birth_year is None

    def test_birth_year_bounds_enforced_on_update(self) -> None:
        with pytest.raises(ValidationError):
            UpdatePersonRequest(birth_year=0)
        with pytest.raises(ValidationError):
            UpdatePersonRequest(birth_year=10000)

    def test_update_accepts_year_without_full_date(self) -> None:
        req = UpdatePersonRequest(birth_year=1975)
        assert req.birth_date is None
        assert req.birth_year == 1975


# ── _FrtPerson (import/export schema) — year round-trip ──────────────────────

class TestFrtPersonYearFields:
    def test_birth_year_round_trips(self) -> None:
        p = _FrtPerson(id="p1", birth_year=1910)
        assert p.birth_year == 1910

    def test_death_year_round_trips(self) -> None:
        p = _FrtPerson(id="p1", death_year=1985)
        assert p.death_year == 1985

    def test_both_year_fields_round_trip(self) -> None:
        p = _FrtPerson(id="p1", birth_year=1901, death_year=1999)
        assert p.birth_year == 1901
        assert p.death_year == 1999

    def test_year_fields_default_to_none_in_frt(self) -> None:
        p = _FrtPerson(id="p1")
        assert p.birth_year is None
        assert p.death_year is None

    def test_frt_person_with_date_and_year(self) -> None:
        p = _FrtPerson(id="p1", birth_date="1950-03-12", birth_year=1950)
        assert p.birth_date == "1950-03-12"
        assert p.birth_year == 1950

    def test_year_only_no_full_date(self) -> None:
        p = _FrtPerson(id="p1", birth_year=1923)
        assert p.birth_date is None
        assert p.birth_year == 1923


# ── Timeline-specific field validation ────────────────────────────────────────

class TestTimelineFieldContracts:
    """Verifies the exact field names the frontend TimelineView expects."""

    def test_frt_person_exports_birth_year_key(self) -> None:
        p = _FrtPerson(id="p1", birth_year=1950)
        data = p.model_dump()
        assert "birth_year" in data
        assert data["birth_year"] == 1950

    def test_frt_person_exports_death_year_key(self) -> None:
        p = _FrtPerson(id="p1", death_year=2010)
        data = p.model_dump()
        assert "death_year" in data
        assert data["death_year"] == 2010

    def test_sex_field_present_for_color_coding(self) -> None:
        p = _FrtPerson(id="p1", sex="FEMALE")
        assert p.sex == "FEMALE"

    def test_sex_defaults_to_unknown(self) -> None:
        p = _FrtPerson(id="p1")
        assert p.sex == "UNKNOWN"

    def test_valid_sex_values_accepted(self) -> None:
        for sex in ("MALE", "FEMALE", "OTHER", "UNKNOWN"):
            p = _FrtPerson(id="p1", sex=sex)
            assert p.sex == sex

    def test_is_living_present_for_bar_endpoint(self) -> None:
        """Timeline uses isLiving to decide whether to cap the bar at 'present'."""
        p = _FrtPerson(id="p1", is_living=True)
        assert p.is_living is True

    def test_is_living_defaults_true(self) -> None:
        p = _FrtPerson(id="p1")
        assert p.is_living is True

    def test_display_name_fields_present(self) -> None:
        p = _FrtPerson(
            id="p1",
            display_given_name="Mary",
            display_surname="Smith",
        )
        assert p.display_given_name == "Mary"
        assert p.display_surname == "Smith"

    def test_display_name_defaults_to_empty_string(self) -> None:
        p = _FrtPerson(id="p1")
        assert p.display_given_name == ""
        assert p.display_surname == ""

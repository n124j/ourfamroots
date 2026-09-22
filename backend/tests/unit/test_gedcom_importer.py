"""Unit tests for src/infrastructure/gedcom/importer.py — pure parsing logic,
no DB required."""
from __future__ import annotations

import pytest

from src.infrastructure.gedcom.importer import GedcomParseError, parse_gedcom

_HEADER = """0 HEAD
1 SOUR TestSource
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
"""
_TRAILER = "0 TRLR\n"


def _ged(body: str) -> bytes:
    return (_HEADER + body + _TRAILER).encode("utf-8")


class TestParseGedcom:
    def test_parses_names_and_exact_dates(self):
        persons, fgs = parse_gedcom(_ged(
            "0 @I1@ INDI\n"
            "1 NAME John /Smith/\n"
            "1 SEX M\n"
            "1 BIRT\n"
            "2 DATE 12 JAN 1950\n"
        ))
        assert len(persons) == 1
        p = persons[0]
        assert p["id"] == "@I1@"
        assert p["display_given_name"] == "John"
        assert p["display_surname"] == "Smith"
        assert p["sex"] == "MALE"
        assert p["birth_date"] == "1950-01-12"
        assert p["birth_year"] == 1950
        assert p["is_living"] is True
        assert p["is_deceased"] is False
        assert fgs == []

    def test_approximate_date_falls_back_to_year_only(self):
        persons, _ = parse_gedcom(_ged(
            "0 @I1@ INDI\n"
            "1 NAME Jane /Doe/\n"
            "1 SEX F\n"
            "1 BIRT\n"
            "2 DATE ABT 1952\n"
        ))
        p = persons[0]
        assert p["birth_date"] is None
        assert p["birth_year"] == 1952

    def test_death_tag_marks_deceased_and_not_living(self):
        persons, _ = parse_gedcom(_ged(
            "0 @I1@ INDI\n"
            "1 NAME Old /Person/\n"
            "1 DEAT\n"
            "2 DATE 3 MAR 2010\n"
        ))
        p = persons[0]
        assert p["is_deceased"] is True
        assert p["is_living"] is False
        assert p["death_date"] == "2010-03-03"

    def test_no_death_tag_defaults_to_living(self):
        persons, _ = parse_gedcom(_ged(
            "0 @I1@ INDI\n"
            "1 NAME Young /Person/\n"
        ))
        p = persons[0]
        assert p["is_living"] is True
        assert p["is_deceased"] is False

    @pytest.mark.parametrize("gedcom_sex,expected", [("M", "MALE"), ("F", "FEMALE"), ("X", "OTHER")])
    def test_sex_mapping(self, gedcom_sex, expected):
        persons, _ = parse_gedcom(_ged(
            f"0 @I1@ INDI\n1 NAME A /B/\n1 SEX {gedcom_sex}\n"
        ))
        assert persons[0]["sex"] == expected

    def test_missing_sex_tag_maps_to_unknown(self):
        persons, _ = parse_gedcom(_ged("0 @I1@ INDI\n1 NAME A /B/\n"))
        assert persons[0]["sex"] == "UNKNOWN"

    def test_family_links_parents_and_children(self):
        persons, fgs = parse_gedcom(_ged(
            "0 @I1@ INDI\n1 NAME Dad /Smith/\n1 SEX M\n"
            "0 @I2@ INDI\n1 NAME Mom /Doe/\n1 SEX F\n"
            "0 @I3@ INDI\n1 NAME Kid /Smith/\n1 SEX M\n"
            "0 @F1@ FAM\n1 HUSB @I1@\n1 WIFE @I2@\n1 CHIL @I3@\n"
        ))
        assert len(persons) == 3
        assert len(fgs) == 1
        fg = fgs[0]
        assert fg["parent_ids"] == ["@I1@", "@I2@"]
        assert fg["children"] == {"@I3@": "BIOLOGICAL"}
        assert fg["union_type"] == "UNKNOWN"  # no MARR tag
        assert fg["is_divorced"] is False

    def test_marr_and_div_tags(self):
        _, fgs = parse_gedcom(_ged(
            "0 @I1@ INDI\n1 NAME Dad /Smith/\n"
            "0 @I2@ INDI\n1 NAME Mom /Doe/\n"
            "0 @F1@ FAM\n1 HUSB @I1@\n1 WIFE @I2@\n"
            "1 MARR\n2 DATE 20 JUN 1974\n"
            "1 DIV\n2 DATE 1 JAN 1990\n"
        ))
        fg = fgs[0]
        assert fg["union_type"] == "MARRIAGE"
        assert fg["is_divorced"] is True
        assert fg["union_date"] == "1974-06-20"

    def test_raises_on_unreadable_file(self):
        with pytest.raises(GedcomParseError):
            parse_gedcom(b"this is not a gedcom file at all")

    def test_raises_when_no_individuals(self):
        with pytest.raises(GedcomParseError, match="no individuals"):
            parse_gedcom(_ged(""))

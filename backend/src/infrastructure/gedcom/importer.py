"""GEDCOM (.ged) parsing — maps INDI/FAM records to the same persons_raw /
fgs_raw dict shapes `_create_tree_from_ofr_data` already expects (the shared
helper also used by `.zip` import and AI tree import), so a GEDCOM import
reuses that exact tree-creation path rather than a parallel one.

v1 scope, deliberately: person names, sex, birth/death dates (exact where
the GEDCOM date is a single day/month/year, year-only for anything
approximate/ranged like "ABT 1952" or "BET 1980 AND 1985"), parent-child and
spousal links, and MARR/DIV presence. Not imported: embedded media (OBJE —
photos live in S3, not this format), source citations, and per-child
pedigree (PEDI, e.g. "adopted" vs "birth" — every child is recorded as
BIOLOGICAL). These are real GEDCOM features some exports use, left for a
later pass rather than implied by this one.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any

from ged4py import GedcomReader
from ged4py.date import DateValueTypes

_GEDCOM_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

_SEX_MAP = {"M": "MALE", "F": "FEMALE", "X": "OTHER"}


class GedcomParseError(ValueError):
    """Raised when the uploaded file isn't a readable GEDCOM document, or
    contains no individuals — the caller maps this to a 422 response."""


def _parse_date_tag(date_tag: Any) -> tuple[str | None, int | None]:
    """Return (iso_date, year) from a ged4py DATE sub-tag. `iso_date` is only
    set for an exact day/month/year (GEDCOM DateValueTypes.SIMPLE) — anything
    approximate or ranged (ABT, BEFORE/AFTER, a BET...AND range, ...) only
    ever yields a year, and only when one is actually present."""
    if date_tag is None or date_tag.value is None:
        return None, None
    dv = date_tag.value
    gdate = getattr(dv, "date", None) or getattr(dv, "date1", None)
    if gdate is None:
        return None, None
    year = getattr(gdate, "year", None)
    iso = None
    if dv.kind == DateValueTypes.SIMPLE:
        month_abbr = getattr(gdate, "month", None)
        day = getattr(gdate, "day", None)
        month = _GEDCOM_MONTHS.get(str(month_abbr).upper()) if month_abbr else None
        if year and month and day:
            try:
                iso = date(year, month, day).isoformat()
            except ValueError:
                iso = None
    return iso, year


def _person_from_indi(indi: Any) -> dict:
    name = indi.name
    sex_tag = indi.sub_tag("SEX")
    sex_raw = (sex_tag.value or "").upper() if sex_tag else ""

    birt = indi.sub_tag("BIRT")
    birth_date, birth_year = _parse_date_tag(birt.sub_tag("DATE") if birt else None)
    deat = indi.sub_tag("DEAT")
    death_date, death_year = _parse_date_tag(deat.sub_tag("DATE") if deat else None)

    return {
        "id": indi.xref_id,
        "display_given_name": (name.first or "").strip() if name else "",
        "display_surname": (name.surname or "").strip() if name else "",
        "sex": _SEX_MAP.get(sex_raw, "UNKNOWN"),
        "is_living": deat is None,
        "is_deceased": deat is not None,
        "birth_date": birth_date,
        "birth_year": birth_year,
        "death_date": death_date,
        "death_year": death_year,
    }


def _family_group_from_fam(fam: Any) -> dict:
    husb = fam.sub_tag("HUSB")
    wife = fam.sub_tag("WIFE")
    parent_ids = [xid for xid in (getattr(husb, "xref_id", None), getattr(wife, "xref_id", None)) if xid]

    children = {}
    for c in fam.sub_tags("CHIL"):
        xid = getattr(c, "xref_id", None)
        if xid:
            children[xid] = "BIOLOGICAL"

    marr = fam.sub_tag("MARR")
    div = fam.sub_tag("DIV")
    union_date, union_date_year = _parse_date_tag(marr.sub_tag("DATE") if marr else None)

    return {
        "id": fam.xref_id,
        "union_type": "MARRIAGE" if marr is not None else "UNKNOWN",
        "is_divorced": div is not None,
        "union_date": union_date,
        "union_date_year": union_date_year,
        "parent_ids": parent_ids,
        "children": children,
    }


def parse_gedcom(raw: bytes) -> tuple[list[dict], list[dict]]:
    """Parse a GEDCOM file's raw bytes into (persons_raw, fgs_raw) — the same
    shape `_create_tree_from_ofr_data` (api/v1/collaboration.py) expects.
    Raises GedcomParseError on anything unreadable or with no individuals."""
    try:
        with GedcomReader(io.BytesIO(raw)) as reader:
            persons = [_person_from_indi(indi) for indi in reader.records0("INDI")]
            family_groups = [_family_group_from_fam(fam) for fam in reader.records0("FAM")]
    except GedcomParseError:
        raise
    except Exception as exc:
        raise GedcomParseError(f"Could not parse GEDCOM file: {exc}") from exc

    if not persons:
        raise GedcomParseError("GEDCOM file contains no individuals (INDI records)")

    return persons, family_groups

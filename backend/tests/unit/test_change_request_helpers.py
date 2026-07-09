"""Unit tests for the pure (non-DB) helper functions in change_requests.py —
the "Propose changes" / review-diff / revert feature.

These are the building blocks behind the diff shown in the review modal and
the tree-canvas highlighting: name formatting, JSON-safe value conversion,
date round-tripping through a JSONB snapshot, and the union/parent-child
edge-set diffing that powers "added"/"removed" relationship detection.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from types import SimpleNamespace

from src.api.v1.change_requests import (
    _actor_name,
    _full_name,
    _group_edges,
    _jsonable,
    _to_date,
)


# ── _actor_name ────────────────────────────────────────────────────────────

class TestActorName:
    def test_uses_given_and_family_name(self):
        user = SimpleNamespace(given_name="Jane", family_name="Doe", email="jane@example.com")
        assert _actor_name(user) == "Jane Doe"

    def test_falls_back_to_email_when_both_names_blank(self):
        user = SimpleNamespace(given_name="", family_name=None, email="jane@example.com")
        assert _actor_name(user) == "jane@example.com"

    def test_trims_when_only_given_name_present(self):
        user = SimpleNamespace(given_name="Jane", family_name=None, email="jane@example.com")
        assert _actor_name(user) == "Jane"


# ── _full_name ─────────────────────────────────────────────────────────────

class TestFullName:
    def test_combines_given_and_surname(self):
        r = SimpleNamespace(display_given_name="John", display_surname="Smith")
        assert _full_name(r) == "John Smith"

    def test_returns_unnamed_when_both_blank(self):
        r = SimpleNamespace(display_given_name="", display_surname=None)
        assert _full_name(r) == "Unnamed"

    def test_trims_when_only_surname_present(self):
        r = SimpleNamespace(display_given_name=None, display_surname="Smith")
        assert _full_name(r) == "Smith"


# ── _jsonable ──────────────────────────────────────────────────────────────

class TestJsonable:
    def test_date_converted_to_iso_string(self):
        assert _jsonable(date(2020, 1, 15)) == "2020-01-15"

    def test_datetime_converted_to_iso_string(self):
        assert _jsonable(datetime(2020, 1, 15, 10, 30)) == "2020-01-15T10:30:00"

    def test_plain_values_pass_through_unchanged(self):
        assert _jsonable("hello") == "hello"
        assert _jsonable(42) == 42
        assert _jsonable(True) is True
        assert _jsonable(None) is None


# ── _to_date ───────────────────────────────────────────────────────────────

class TestToDate:
    def test_parses_iso_string(self):
        assert _to_date("2020-01-15") == date(2020, 1, 15)

    def test_passes_through_non_string_unchanged(self):
        d = date(2020, 1, 15)
        assert _to_date(d) is d

    def test_passes_through_none_unchanged(self):
        assert _to_date(None) is None

    def test_round_trips_through_jsonable(self):
        """This is the exact round trip a snapshot goes through: a DB date
        gets JSON-serialised via _jsonable() for storage in the audit log,
        then parsed back via _to_date() when a revert restores it."""
        original = date(1955, 3, 2)
        assert _to_date(_jsonable(original)) == original


# ── _group_edges ───────────────────────────────────────────────────────────

def _uid() -> uuid.UUID:
    return uuid.uuid4()


class TestGroupEdges:
    def test_empty_groups_yield_empty_edges(self):
        unions, links = _group_edges([])
        assert unions == set()
        assert links == set()

    def test_single_parent_union_and_one_child(self):
        parent = _uid()
        child = _uid()
        groups = [{"parents": {parent}, "children": {child}}]
        unions, links = _group_edges(groups)
        pkey = (str(parent),)
        assert unions == {pkey}
        assert links == {(pkey, str(child))}

    def test_two_parent_union_is_order_independent(self):
        """Parent order in the source data shouldn't matter — the sorted
        tuple key must be the same whichever order the two parents load in,
        or the diff would spuriously report the same union as added+removed."""
        p1, p2 = _uid(), _uid()
        groups_a = [{"parents": {p1, p2}, "children": {}}]
        groups_b = [{"parents": {p2, p1}, "children": {}}]
        unions_a, _ = _group_edges(groups_a)
        unions_b, _ = _group_edges(groups_b)
        assert unions_a == unions_b

    def test_multiple_children_each_get_their_own_link(self):
        parent = _uid()
        c1, c2 = _uid(), _uid()
        groups = [{"parents": {parent}, "children": {c1, c2}}]
        _, links = _group_edges(groups)
        pkey = (str(parent),)
        assert links == {(pkey, str(c1)), (pkey, str(c2))}

    def test_group_with_no_parents_still_yields_empty_parent_key(self):
        """A parentless group (e.g. a lone child row with no union yet)
        still produces a union entry — callers filter out the empty-tuple
        key explicitly when they don't want to count it as a real union."""
        child = _uid()
        groups = [{"parents": set(), "children": {child}}]
        unions, links = _group_edges(groups)
        assert () in unions
        assert ((), str(child)) in links

    def test_diffing_added_and_removed_unions(self):
        """This is exactly how the review diff computes unions_added/removed:
        set difference between the original tree's edges and the draft's."""
        shared_parent = _uid()
        new_parent = _uid()
        removed_parent = _uid()

        orig_unions, _ = _group_edges([
            {"parents": {shared_parent, removed_parent}, "children": {}},
        ])
        draft_unions, _ = _group_edges([
            {"parents": {shared_parent, new_parent}, "children": {}},
        ])

        added = draft_unions - orig_unions
        removed = orig_unions - draft_unions
        assert added == {tuple(sorted(str(p) for p in (shared_parent, new_parent)))}
        assert removed == {tuple(sorted(str(p) for p in (shared_parent, removed_parent)))}

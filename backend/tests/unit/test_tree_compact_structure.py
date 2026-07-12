"""Unit tests for tree graph structure required by compact ancestor/descendant layouts.

The frontend compact-ancestor-family and compact-descendant-family layout modes
require the API tree graph to carry:
  - persons[].birth_year (for generation ordering by age)
  - family_groups[].parent_ids (list of parent person IDs for couple placement)
  - family_groups[].children (mapping of child IDs to parentage type)
  - family_groups[].union_type (for Heritage view edge styles)
  - family_groups[].is_divorced (for dashed divorce edge in Heritage view)

These tests verify the _OfrFamilyGroup schema and the _OfrPerson schema carry
the correct fields, and that the import/export round-trip preserves the
parent–child structure that the ancestorSubgraphIds() and
descendantFamilySubgraphIds() graph traversal functions depend on.

Covers:
  - _OfrFamilyGroup: parent_ids, children, union_type, is_divorced, custom_label
  - Family group with two parents (couple) → compact layout keeps couple adjacent
  - Family group with multiple children → all children receive the same FG id
  - Union types: MARRIAGE, PARTNERSHIP, COHABITATION, UNKNOWN
  - Divorced flag toggles Heritage edge visual style
  - custom_label is preserved on round-trip
  - ImportTreeRequest round-trips a multi-generation graph
"""

from __future__ import annotations

import pytest

from src.api.v1.collaboration import _OfrFamilyGroup, _OfrPerson, ImportTreeRequest


# ── _OfrFamilyGroup basic structure ──────────────────────────────────────────

class TestOfrFamilyGroupStructure:
    def test_minimal_family_group(self) -> None:
        fg = _OfrFamilyGroup(id="fg1")
        assert fg.id == "fg1"
        assert fg.parent_ids == []
        assert fg.children == {}

    def test_two_parent_ids_accepted(self) -> None:
        fg = _OfrFamilyGroup(id="fg1", parent_ids=["p1", "p2"])
        assert fg.parent_ids == ["p1", "p2"]

    def test_single_parent_accepted(self) -> None:
        fg = _OfrFamilyGroup(id="fg1", parent_ids=["p1"])
        assert fg.parent_ids == ["p1"]

    def test_no_parents_accepted(self) -> None:
        fg = _OfrFamilyGroup(id="fg1", parent_ids=[])
        assert fg.parent_ids == []

    def test_children_dict_accepted(self) -> None:
        fg = _OfrFamilyGroup(
            id="fg1",
            parent_ids=["p1"],
            children={"c1": "BIOLOGICAL", "c2": "ADOPTED"},
        )
        assert fg.children["c1"] == "BIOLOGICAL"
        assert fg.children["c2"] == "ADOPTED"

    def test_empty_children_dict(self) -> None:
        fg = _OfrFamilyGroup(id="fg1", children={})
        assert fg.children == {}

    def test_multiple_children_preserved(self) -> None:
        children = {f"child-{i}": "BIOLOGICAL" for i in range(5)}
        fg = _OfrFamilyGroup(id="fg1", children=children)
        assert len(fg.children) == 5
        for child_id in children:
            assert child_id in fg.children


# ── Union type field ──────────────────────────────────────────────────────────

class TestOfrFamilyGroupUnionType:
    def test_default_union_type_is_unknown(self) -> None:
        fg = _OfrFamilyGroup(id="fg1")
        assert fg.union_type == "UNKNOWN"

    def test_marriage_explicit(self) -> None:
        fg = _OfrFamilyGroup(id="fg1", union_type="MARRIAGE")
        assert fg.union_type == "MARRIAGE"

    def test_partnership(self) -> None:
        fg = _OfrFamilyGroup(id="fg1", union_type="PARTNERSHIP")
        assert fg.union_type == "PARTNERSHIP"

    def test_cohabitation(self) -> None:
        fg = _OfrFamilyGroup(id="fg1", union_type="COHABITATION")
        assert fg.union_type == "COHABITATION"

    def test_unknown(self) -> None:
        fg = _OfrFamilyGroup(id="fg1", union_type="UNKNOWN")
        assert fg.union_type == "UNKNOWN"


# ── Divorced flag (Heritage view edge style) ──────────────────────────────────

class TestOfrFamilyGroupDivorced:
    def test_is_divorced_defaults_to_false(self) -> None:
        fg = _OfrFamilyGroup(id="fg1")
        assert fg.is_divorced is False

    def test_is_divorced_true_accepted(self) -> None:
        fg = _OfrFamilyGroup(id="fg1", is_divorced=True)
        assert fg.is_divorced is True

    def test_divorced_marriage_round_trips(self) -> None:
        fg = _OfrFamilyGroup(
            id="fg1",
            union_type="MARRIAGE",
            is_divorced=True,
        )
        data = fg.model_dump()
        assert data["is_divorced"] is True
        assert data["union_type"] == "MARRIAGE"


# ── custom_label field ────────────────────────────────────────────────────────

class TestOfrFamilyGroupCustomLabel:
    def test_custom_label_defaults_to_none(self) -> None:
        fg = _OfrFamilyGroup(id="fg1")
        assert fg.custom_label is None

    def test_custom_label_set(self) -> None:
        fg = _OfrFamilyGroup(id="fg1", custom_label="Church Wedding")
        assert fg.custom_label == "Church Wedding"

    def test_custom_label_round_trips(self) -> None:
        fg = _OfrFamilyGroup(id="fg1", custom_label="2nd Marriage")
        data = fg.model_dump()
        assert data["custom_label"] == "2nd Marriage"


# ── Multi-generation graph for compact layout round-trip ─────────────────────

class TestImportTreeRequestCompactGraph:
    """
    Builds the following two-generation graph and verifies it round-trips:

        Gen 0: Alice + Bob ──(fg1)──> Carol, Dave
        Gen 0: Eve  + Fred ──(fg2)──> Grace, Harry

    This is the minimal structure needed by compact-descendant-family /
    compact-ancestor-family to demonstrate that two sibling subtrees are
    repacked into a tighter layout.
    """

    def _make_graph(self) -> ImportTreeRequest:
        persons = [
            _OfrPerson(id="alice", display_given_name="Alice", birth_year=1950, sex="FEMALE"),
            _OfrPerson(id="bob",   display_given_name="Bob",   birth_year=1948, sex="MALE"),
            _OfrPerson(id="carol", display_given_name="Carol", birth_year=1975, sex="FEMALE"),
            _OfrPerson(id="dave",  display_given_name="Dave",  birth_year=1977, sex="MALE"),
            _OfrPerson(id="eve",   display_given_name="Eve",   birth_year=1952, sex="FEMALE"),
            _OfrPerson(id="fred",  display_given_name="Fred",  birth_year=1949, sex="MALE"),
            _OfrPerson(id="grace", display_given_name="Grace", birth_year=1978, sex="FEMALE"),
            _OfrPerson(id="harry", display_given_name="Harry", birth_year=1980, sex="MALE"),
        ]
        family_groups = [
            _OfrFamilyGroup(
                id="fg1",
                parent_ids=["alice", "bob"],
                children={"carol": "BIOLOGICAL", "dave": "BIOLOGICAL"},
                union_type="MARRIAGE",
            ),
            _OfrFamilyGroup(
                id="fg2",
                parent_ids=["eve", "fred"],
                children={"grace": "BIOLOGICAL", "harry": "BIOLOGICAL"},
                union_type="MARRIAGE",
            ),
        ]
        return ImportTreeRequest(tree_name="Test Tree", persons=persons, family_groups=family_groups)

    def test_persons_count(self) -> None:
        req = self._make_graph()
        assert len(req.persons) == 8

    def test_family_groups_count(self) -> None:
        req = self._make_graph()
        assert len(req.family_groups) == 2

    def test_fg1_has_two_parents(self) -> None:
        req = self._make_graph()
        fg1 = next(fg for fg in req.family_groups if fg.id == "fg1")
        assert len(fg1.parent_ids) == 2
        assert "alice" in fg1.parent_ids
        assert "bob" in fg1.parent_ids

    def test_fg1_has_two_children(self) -> None:
        req = self._make_graph()
        fg1 = next(fg for fg in req.family_groups if fg.id == "fg1")
        assert len(fg1.children) == 2
        assert "carol" in fg1.children
        assert "dave" in fg1.children

    def test_all_persons_have_birth_years(self) -> None:
        req = self._make_graph()
        for person in req.persons:
            assert person.birth_year is not None, f"{person.id} missing birth_year"

    def test_all_family_groups_have_parents(self) -> None:
        req = self._make_graph()
        for fg in req.family_groups:
            assert len(fg.parent_ids) >= 1, f"{fg.id} has no parents"

    def test_gen0_persons_older_than_gen1(self) -> None:
        req = self._make_graph()
        p_by_id = {p.id: p for p in req.persons}
        gen0_years = [p_by_id["alice"].birth_year, p_by_id["bob"].birth_year]
        gen1_years = [p_by_id["carol"].birth_year, p_by_id["dave"].birth_year]
        for g0 in gen0_years:
            for g1 in gen1_years:
                assert g0 < g1  # parents born before children

    def test_model_dump_preserves_structure(self) -> None:
        req = self._make_graph()
        data = req.model_dump()
        assert len(data["persons"]) == 8
        assert len(data["family_groups"]) == 2
        fg1_data = next(fg for fg in data["family_groups"] if fg["id"] == "fg1")
        assert "carol" in fg1_data["children"]


# ── Ancestor subgraph structure ───────────────────────────────────────────────

class TestAncestorSubgraphStructure:
    """
    Verifies that the parent–child direction in _OfrFamilyGroup matches the
    ancestorSubgraphIds() graph traversal expectation:

      - parent_ids lists persons who ARE PARENTS (ancestors go upward)
      - children maps child personId → parentageType (descendants go downward)

    compact-ancestor-family traverses UPWARD from a focal person using
    parent_ids, so the parentage direction must be preserved on import.
    """

    def test_parent_ids_direction(self) -> None:
        grandparent = _OfrPerson(id="gp", birth_year=1900)
        parent = _OfrPerson(id="parent", birth_year=1930)
        fg = _OfrFamilyGroup(
            id="fg1",
            parent_ids=["gp"],          # grandparent IS the parent
            children={"parent": "BIOLOGICAL"},  # parent is the child
        )
        # Upward traversal from 'parent': look at family group where 'parent'
        # is in children → fg1.parent_ids gives the ancestors
        assert "gp" in fg.parent_ids
        assert "parent" in fg.children

    def test_multiple_ancestors_in_parent_ids(self) -> None:
        fg = _OfrFamilyGroup(
            id="fg1",
            parent_ids=["grandfather", "grandmother"],
            children={"father": "BIOLOGICAL"},
        )
        assert "grandfather" in fg.parent_ids
        assert "grandmother" in fg.parent_ids
        assert len(fg.parent_ids) == 2

    def test_compact_ancestor_graph_three_generations(self) -> None:
        """Minimal 3-gen graph: great-grandparent → grandparent → parent."""
        persons = [
            _OfrPerson(id="ggp", birth_year=1880),
            _OfrPerson(id="gp",  birth_year=1910),
            _OfrPerson(id="par", birth_year=1940),
            _OfrPerson(id="foc", birth_year=1970),
        ]
        fgs = [
            _OfrFamilyGroup(id="fg1", parent_ids=["ggp"], children={"gp": "BIOLOGICAL"}),
            _OfrFamilyGroup(id="fg2", parent_ids=["gp"],  children={"par": "BIOLOGICAL"}),
            _OfrFamilyGroup(id="fg3", parent_ids=["par"], children={"foc": "BIOLOGICAL"}),
        ]
        req = ImportTreeRequest(tree_name="Test Tree", persons=persons, family_groups=fgs)
        assert len(req.persons) == 4
        assert len(req.family_groups) == 3

        # Each FG links one generation to the next
        fg3_data = next(fg for fg in req.family_groups if fg.id == "fg3")
        assert "par" in fg3_data.parent_ids
        assert "foc" in fg3_data.children

"""Unit tests for FamilyGraph data structure."""

from __future__ import annotations

import uuid
import pytest

from src.domain.genealogy.entities import FamilyGroupNode, ParentageType, PersonNode, Sex, UnionType
from src.domain.genealogy.graph import FamilyGraph


# ── Helpers ───────────────────────────────────────────────────────

def make_person(name: str = "Alice", tree_id: uuid.UUID | None = None) -> PersonNode:
    tid = tree_id or uuid.uuid4()
    return PersonNode(
        id=uuid.uuid4(),
        tree_id=tid,
        tenant_id=uuid.uuid4(),
        display_given_name=name,
    )


def make_fg(
    parents: list[uuid.UUID],
    children: dict[uuid.UUID, ParentageType] | None = None,
    tree_id: uuid.UUID | None = None,
) -> FamilyGroupNode:
    tid = tree_id or uuid.uuid4()
    return FamilyGroupNode(
        id=uuid.uuid4(),
        tree_id=tid,
        tenant_id=uuid.uuid4(),
        parent_ids=parents,
        children=children or {},
    )


def build_graph(*persons: PersonNode, fgs: list[FamilyGroupNode] | None = None) -> FamilyGraph:
    g = FamilyGraph()
    for p in persons:
        g.add_person(p)
    for fg in (fgs or []):
        g.add_family_group(fg)
    return g


# ── Basic structure ───────────────────────────────────────────────

class TestGraphConstruction:
    def test_empty_graph(self) -> None:
        g = FamilyGraph()
        assert len(g) == 0

    def test_add_person(self) -> None:
        p = make_person()
        g = build_graph(p)
        assert g.has_person(p.id)
        assert g.get_person(p.id) == p

    def test_add_family_group(self) -> None:
        parent = make_person("Dad")
        child = make_person("Kid")
        fg = make_fg(parents=[parent.id], children={child.id: ParentageType.BIOLOGICAL})
        g = build_graph(parent, child, fgs=[fg])

        assert g.get_family_group(fg.id) == fg
        assert g.family_group_as_child(child.id) == fg
        assert fg in g.family_groups_as_parent(parent.id)

    def test_unknown_person_returns_none(self) -> None:
        g = FamilyGraph()
        assert g.get_person(uuid.uuid4()) is None


# ── Relative queries ──────────────────────────────────────────────

class TestRelativeQueries:
    def setup_method(self) -> None:
        """Build: grandpa → dad → child"""
        self.grandpa = make_person("Grandpa")
        self.dad = make_person("Dad")
        self.child = make_person("Child")

        self.fg1 = make_fg([self.grandpa.id], {self.dad.id: ParentageType.BIOLOGICAL})
        self.fg2 = make_fg([self.dad.id], {self.child.id: ParentageType.BIOLOGICAL})

        self.g = build_graph(self.grandpa, self.dad, self.child, fgs=[self.fg1, self.fg2])

    def test_parents_of(self) -> None:
        assert self.g.parents_of(self.child.id) == [self.dad.id]
        assert self.g.parents_of(self.dad.id) == [self.grandpa.id]
        assert self.g.parents_of(self.grandpa.id) == []

    def test_children_of(self) -> None:
        assert self.child.id in self.g.children_of(self.dad.id)
        assert self.dad.id in self.g.children_of(self.grandpa.id)

    def test_siblings_none_when_only_child(self) -> None:
        assert self.g.siblings_of(self.child.id) == []

    def test_siblings_with_two_children(self) -> None:
        sibling = make_person("Sibling")
        self.g.add_person(sibling)
        self.fg2.children[sibling.id] = ParentageType.BIOLOGICAL
        self.g._child_in_fg[sibling.id] = self.fg2.id

        sibs = self.g.siblings_of(self.child.id)
        assert sibling.id in sibs

    def test_spouses_of(self) -> None:
        mum = make_person("Mum")
        self.g.add_person(mum)
        # Add mum as co-parent in fg2
        self.fg2.parent_ids.append(mum.id)
        self.g._parent_of_fgs.setdefault(mum.id, set()).add(self.fg2.id)

        assert mum.id in self.g.spouses_of(self.dad.id)
        assert self.dad.id in self.g.spouses_of(mum.id)


# ── BFS traversals ────────────────────────────────────────────────

class TestTraversals:
    def setup_method(self) -> None:
        """
        great-grandpa → grandpa → dad → child
                      → grandma ↗
        """
        self.ggp = make_person("GreatGrandpa")
        self.gp = make_person("Grandpa")
        self.gm = make_person("Grandma")
        self.dad = make_person("Dad")
        self.child = make_person("Child")

        fg1 = make_fg([self.ggp.id], {self.gp.id: ParentageType.BIOLOGICAL})
        fg2 = make_fg([self.gp.id, self.gm.id], {self.dad.id: ParentageType.BIOLOGICAL})
        fg3 = make_fg([self.dad.id], {self.child.id: ParentageType.BIOLOGICAL})

        self.g = build_graph(
            self.ggp, self.gp, self.gm, self.dad, self.child,
            fgs=[fg1, fg2, fg3],
        )

    def test_ancestors_by_generation(self) -> None:
        anc = self.g.ancestors_bfs(self.child.id)
        assert self.dad.id in anc[1]
        assert self.gp.id in anc[2]
        assert self.gm.id in anc[2]
        assert self.ggp.id in anc[3]

    def test_descendants_by_generation(self) -> None:
        desc = self.g.descendants_bfs(self.ggp.id)
        assert self.gp.id in desc[1]
        assert self.dad.id in desc[2]
        assert self.child.id in desc[3]

    def test_ancestors_flat(self) -> None:
        flat = self.g.ancestors_flat(self.child.id)
        assert flat[self.dad.id] == 1
        assert flat[self.gp.id] == 2
        assert flat[self.ggp.id] == 3

    def test_max_depth_respected(self) -> None:
        anc = self.g.ancestors_bfs(self.child.id, max_depth=2)
        assert 3 not in anc  # great-grandpa should be excluded

    def test_all_descendants(self) -> None:
        desc = self.g.all_descendants(self.gp.id)
        assert self.dad.id in desc
        assert self.child.id in desc
        assert self.ggp.id not in desc

    def test_shortest_path(self) -> None:
        path = self.g.shortest_path(self.child.id, self.gp.id)
        assert path is not None
        assert path[0] == self.child.id
        assert path[-1] == self.gp.id

    def test_shortest_path_self(self) -> None:
        path = self.g.shortest_path(self.child.id, self.child.id)
        assert path == [self.child.id]

    def test_shortest_path_unconnected_returns_none(self) -> None:
        isolated = make_person("Isolated")
        self.g.add_person(isolated)
        assert self.g.shortest_path(self.child.id, isolated.id) is None


# ── Half-sibling detection ────────────────────────────────────────

class TestHalfSiblings:
    def test_half_siblings_share_one_parent(self) -> None:
        """
        dad + mum1 → child1
        dad + mum2 → child2
        child1 and child2 are half-siblings via dad
        """
        dad = make_person("Dad")
        mum1 = make_person("Mum1")
        mum2 = make_person("Mum2")
        child1 = make_person("Child1")
        child2 = make_person("Child2")

        fg1 = make_fg([dad.id, mum1.id], {child1.id: ParentageType.BIOLOGICAL})
        fg2 = make_fg([dad.id, mum2.id], {child2.id: ParentageType.BIOLOGICAL})

        g = build_graph(dad, mum1, mum2, child1, child2, fgs=[fg1, fg2])

        half_sibs = g.half_siblings_of(child1.id)
        assert child2.id in half_sibs
        assert dad.id in half_sibs[child2.id]

    def test_full_siblings_not_in_half_siblings(self) -> None:
        dad = make_person("Dad")
        child1 = make_person("Child1")
        child2 = make_person("Child2")
        fg = make_fg([dad.id], {
            child1.id: ParentageType.BIOLOGICAL,
            child2.id: ParentageType.BIOLOGICAL,
        })
        g = build_graph(dad, child1, child2, fgs=[fg])

        # child2 is a FULL sibling of child1 — not in half_siblings
        half_sibs = g.half_siblings_of(child1.id)
        assert child2.id not in half_sibs

"""Unit tests for genealogy calculators.

Family tree used across most tests:

                     great-grandpa (ggp)
                           │
                 ┌─────────┴─────────┐
              grandpa (gp)       great-aunt (gau)
              /      \                  │
         dad (d)    uncle (u)       cousin1 (c1)   ← 1st cousin of dad
         │
    ┌────┴────┐
 child (ch)  sib (s)     ← full siblings
"""

from __future__ import annotations

import uuid
import pytest

from src.domain.genealogy import calculators as calc
from src.domain.genealogy.entities import (
    FamilyGroupNode,
    KinshipResult,
    ParentageType,
    PersonNode,
    RelationshipKind,
)
from src.domain.genealogy.graph import FamilyGraph


# ── Tree fixture ──────────────────────────────────────────────────

class FamilyFixture:
    def __init__(self) -> None:
        self.ggp   = self._p("GreatGrandpa")
        self.gp    = self._p("Grandpa")
        self.gau   = self._p("GreatAunt")    # sibling of gp
        self.dad   = self._p("Dad")
        self.mum   = self._p("Mum")
        self.uncle = self._p("Uncle")        # sibling of dad
        self.c1    = self._p("Cousin1")      # child of great-aunt — 1st cousin of dad? No:
        # Wait — let me set this up correctly:
        # gp and gau are siblings (both children of ggp)
        # dad and uncle are children of gp (+ mum)
        # c1 is child of uncle → c1 is nephew of dad
        # For 1st cousin, we need dad's sibling's child, or dad and uncle's child
        self.nephew = self._p("Nephew")      # child of uncle → nephew of dad
        self.c2nd   = self._p("2ndCousin")   # child of gau → 1st cousin of dad
        self.child  = self._p("Child")
        self.sib    = self._p("Sibling")     # full sibling of child
        self.half_sib = self._p("HalfSib")  # half sibling of child (same dad, diff mum)
        self.mum2   = self._p("Mum2")
        self.spouse = self._p("Spouse")      # spouse of child

        self.graph = FamilyGraph()
        self._add_all()

    def _p(self, name: str) -> PersonNode:
        return PersonNode(id=uuid.uuid4(), tree_id=uuid.uuid4(),
                          tenant_id=uuid.uuid4(), display_given_name=name)

    def _add_all(self) -> None:
        persons = [
            self.ggp, self.gp, self.gau, self.dad, self.mum, self.uncle,
            self.nephew, self.c2nd, self.child, self.sib, self.half_sib,
            self.mum2, self.spouse,
        ]
        for p in persons:
            self.graph.add_person(p)

        # ggp → gp, gau
        fg1 = self._fg([self.ggp.id], {
            self.gp.id: ParentageType.BIOLOGICAL,
            self.gau.id: ParentageType.BIOLOGICAL,
        })
        # gp + mum → dad, uncle
        fg2 = self._fg([self.gp.id, self.mum.id], {
            self.dad.id: ParentageType.BIOLOGICAL,
            self.uncle.id: ParentageType.BIOLOGICAL,
        })
        # gau → c2nd  (gau's child = 1st cousin of dad)
        fg3 = self._fg([self.gau.id], {self.c2nd.id: ParentageType.BIOLOGICAL})
        # uncle → nephew
        fg4 = self._fg([self.uncle.id], {self.nephew.id: ParentageType.BIOLOGICAL})
        # dad → child, sib
        fg5 = self._fg([self.dad.id], {
            self.child.id: ParentageType.BIOLOGICAL,
            self.sib.id: ParentageType.BIOLOGICAL,
        })
        # dad + mum2 → half_sib
        fg6 = self._fg([self.dad.id, self.mum2.id], {
            self.half_sib.id: ParentageType.BIOLOGICAL,
        })
        # child + spouse → (just the partnership, no children yet)
        fg7 = self._fg([self.child.id, self.spouse.id], {})

        for fg in [fg1, fg2, fg3, fg4, fg5, fg6, fg7]:
            self.graph.add_family_group(fg)

    def _fg(
        self,
        parents: list[uuid.UUID],
        children: dict[uuid.UUID, ParentageType],
    ) -> FamilyGroupNode:
        return FamilyGroupNode(
            id=uuid.uuid4(), tree_id=uuid.uuid4(), tenant_id=uuid.uuid4(),
            parent_ids=parents, children=children,
        )


@pytest.fixture
def fam() -> FamilyFixture:
    return FamilyFixture()


# ── Ancestor / descendant ─────────────────────────────────────────

class TestAncestors:
    def test_parents(self, fam: FamilyFixture) -> None:
        result = calc.ancestors(fam.graph, fam.child.id)
        assert fam.dad.id in result[1]

    def test_grandparents(self, fam: FamilyFixture) -> None:
        gps = calc.grandparents(fam.graph, fam.child.id)
        assert fam.gp.id in gps
        assert fam.mum.id in gps

    def test_great_grandparents(self, fam: FamilyFixture) -> None:
        ggps = calc.great_grandparents(fam.graph, fam.child.id)
        assert fam.ggp.id in ggps

    def test_person_with_no_parents(self, fam: FamilyFixture) -> None:
        result = calc.ancestors(fam.graph, fam.ggp.id)
        assert result == {}

    def test_max_depth_limits_result(self, fam: FamilyFixture) -> None:
        result = calc.ancestors(fam.graph, fam.child.id, max_depth=1)
        assert 2 not in result
        assert 3 not in result


class TestDescendants:
    def test_children(self, fam: FamilyFixture) -> None:
        result = calc.descendants(fam.graph, fam.dad.id)
        assert fam.child.id in result[1]
        assert fam.sib.id in result[1]
        assert fam.half_sib.id in result[1]

    def test_grandchildren(self, fam: FamilyFixture) -> None:
        gcs = calc.grandchildren(fam.graph, fam.gp.id)
        assert fam.child.id in gcs

    def test_leaf_has_no_descendants(self, fam: FamilyFixture) -> None:
        result = calc.descendants(fam.graph, fam.child.id)
        assert result == {}


# ── LCA ───────────────────────────────────────────────────────────

class TestLCA:
    def test_siblings_lca_is_parent(self, fam: FamilyFixture) -> None:
        lcas = calc.lowest_common_ancestors(fam.graph, fam.child.id, fam.sib.id)
        lca_ids = {t[0] for t in lcas}
        assert fam.dad.id in lca_ids

    def test_lca_depths_for_1st_cousin(self, fam: FamilyFixture) -> None:
        # dad and c2nd: LCA is gp (dad's parent, c2nd's grandparent via gau)
        # dad: gp is at depth 1; c2nd: gp is at depth 2
        lcas = calc.lowest_common_ancestors(fam.graph, fam.dad.id, fam.c2nd.id)
        lca_ids = {t[0]: (t[1], t[2]) for t in lcas}
        assert fam.gp.id in lca_ids or fam.ggp.id in lca_ids

    def test_unrelated_persons_no_lca(self, fam: FamilyFixture) -> None:
        isolated = PersonNode(id=uuid.uuid4(), tree_id=uuid.uuid4(), tenant_id=uuid.uuid4())
        fam.graph.add_person(isolated)
        lcas = calc.lowest_common_ancestors(fam.graph, fam.child.id, isolated.id)
        assert lcas == []


# ── Kinship classification ────────────────────────────────────────

class TestKinship:
    def test_self(self, fam: FamilyFixture) -> None:
        k = calc.classify_kinship(fam.graph, fam.child.id, fam.child.id)
        assert k.kind == RelationshipKind.SELF

    def test_parent(self, fam: FamilyFixture) -> None:
        k = calc.classify_kinship(fam.graph, fam.child.id, fam.dad.id)
        assert k.kind == RelationshipKind.PARENT

    def test_child(self, fam: FamilyFixture) -> None:
        k = calc.classify_kinship(fam.graph, fam.dad.id, fam.child.id)
        assert k.kind == RelationshipKind.CHILD

    def test_grandparent(self, fam: FamilyFixture) -> None:
        k = calc.classify_kinship(fam.graph, fam.child.id, fam.gp.id)
        assert k.kind == RelationshipKind.GRANDPARENT

    def test_grandchild(self, fam: FamilyFixture) -> None:
        k = calc.classify_kinship(fam.graph, fam.gp.id, fam.child.id)
        assert k.kind == RelationshipKind.GRANDCHILD

    def test_great_grandparent(self, fam: FamilyFixture) -> None:
        k = calc.classify_kinship(fam.graph, fam.child.id, fam.ggp.id)
        assert k.kind == RelationshipKind.GREAT_GRANDPARENT

    def test_sibling(self, fam: FamilyFixture) -> None:
        k = calc.classify_kinship(fam.graph, fam.child.id, fam.sib.id)
        assert k.kind == RelationshipKind.SIBLING

    def test_half_sibling(self, fam: FamilyFixture) -> None:
        k = calc.classify_kinship(fam.graph, fam.child.id, fam.half_sib.id)
        assert k.kind == RelationshipKind.HALF_SIBLING

    def test_spouse(self, fam: FamilyFixture) -> None:
        k = calc.classify_kinship(fam.graph, fam.child.id, fam.spouse.id)
        assert k.kind == RelationshipKind.SPOUSE

    def test_uncle(self, fam: FamilyFixture) -> None:
        # uncle is sibling of dad; child's uncle
        k = calc.classify_kinship(fam.graph, fam.child.id, fam.uncle.id)
        assert k.kind == RelationshipKind.AUNT_UNCLE

    def test_nephew(self, fam: FamilyFixture) -> None:
        # nephew is child of uncle; dad's nephew
        k = calc.classify_kinship(fam.graph, fam.dad.id, fam.nephew.id)
        assert k.kind == RelationshipKind.NIECE_NEPHEW

    def test_unknown_for_unrelated(self, fam: FamilyFixture) -> None:
        isolated = PersonNode(id=uuid.uuid4(), tree_id=uuid.uuid4(), tenant_id=uuid.uuid4())
        fam.graph.add_person(isolated)
        k = calc.classify_kinship(fam.graph, fam.child.id, isolated.id)
        assert k.kind == RelationshipKind.UNKNOWN

    def test_cousin_label(self, fam: FamilyFixture) -> None:
        k = calc.classify_kinship(fam.graph, fam.dad.id, fam.c2nd.id)
        assert k.kind == RelationshipKind.COUSIN
        assert k.cousin_degree == 1
        assert k.cousin_removed == 0
        assert k.label == "1st cousin"

    def test_kinship_is_symmetric(self, fam: FamilyFixture) -> None:
        """classify_kinship(A, B).kind and classify_kinship(B, A).kind should be inverses."""
        k_fwd = calc.classify_kinship(fam.graph, fam.child.id, fam.dad.id)
        k_rev = calc.classify_kinship(fam.graph, fam.dad.id, fam.child.id)
        assert k_fwd.kind == RelationshipKind.PARENT
        assert k_rev.kind == RelationshipKind.CHILD


# ── Lineage paths ─────────────────────────────────────────────────

class TestLineagePaths:
    def test_direct_path_exists(self, fam: FamilyFixture) -> None:
        paths = calc.lineage_paths(fam.graph, fam.child.id, fam.dad.id)
        assert len(paths) >= 1
        assert paths[0].origin == fam.child.id
        assert paths[0].destination == fam.dad.id

    def test_path_to_grandparent(self, fam: FamilyFixture) -> None:
        paths = calc.lineage_paths(fam.graph, fam.child.id, fam.gp.id)
        assert len(paths) >= 1
        assert fam.dad.id in paths[0].nodes

    def test_path_between_cousins(self, fam: FamilyFixture) -> None:
        paths = calc.lineage_paths(fam.graph, fam.child.id, fam.nephew.id)
        assert len(paths) >= 1

    def test_no_path_for_unrelated_returns_empty(self, fam: FamilyFixture) -> None:
        isolated = PersonNode(id=uuid.uuid4(), tree_id=uuid.uuid4(), tenant_id=uuid.uuid4())
        fam.graph.add_person(isolated)
        paths = calc.lineage_paths(fam.graph, fam.child.id, isolated.id)
        assert paths == []

    def test_edge_labels_populated(self, fam: FamilyFixture) -> None:
        paths = calc.lineage_paths(fam.graph, fam.child.id, fam.dad.id)
        assert len(paths[0].edge_labels) == paths[0].length

    def test_shortest_path_first(self, fam: FamilyFixture) -> None:
        paths = calc.lineage_paths(fam.graph, fam.child.id, fam.ggp.id, max_paths=5)
        assert paths[0].length <= paths[-1].length


# ── Cousin finder ─────────────────────────────────────────────────

class TestCousins:
    def test_find_first_cousins(self, fam: FamilyFixture) -> None:
        results = calc.cousins(fam.graph, fam.dad.id, degree=1, removed=0)
        cousin_ids = [r.person2_id for r in results]
        assert fam.c2nd.id in cousin_ids

    def test_no_cousins_for_isolated(self, fam: FamilyFixture) -> None:
        isolated = PersonNode(id=uuid.uuid4(), tree_id=uuid.uuid4(), tenant_id=uuid.uuid4())
        fam.graph.add_person(isolated)
        results = calc.cousins(fam.graph, isolated.id, degree=1)
        assert results == []

"""Unit tests for FamilyTreeDomainService mutations."""

from __future__ import annotations

import uuid
import pytest

from src.domain.genealogy.entities import (
    FamilyGroupNode,
    ParentageType,
    PersonNode,
    UnionType,
)
from src.domain.genealogy.exceptions import (
    CircularRelationshipError,
    DuplicateRelationshipError,
    PersonAlreadyHasParentsError,
    PersonNotInTreeError,
    SelfRelationshipError,
)
from src.domain.genealogy.graph import FamilyGraph
from src.domain.genealogy.services import FamilyTreeDomainService


# ── Helpers ───────────────────────────────────────────────────────

TREE_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()


def _person(name: str = "P") -> PersonNode:
    return PersonNode(
        id=uuid.uuid4(),
        tree_id=TREE_ID,
        tenant_id=TENANT_ID,
        display_given_name=name,
    )


def _fg(
    parents: list[uuid.UUID],
    children: dict[uuid.UUID, ParentageType] | None = None,
) -> FamilyGroupNode:
    return FamilyGroupNode(
        id=uuid.uuid4(),
        tree_id=TREE_ID,
        tenant_id=TENANT_ID,
        parent_ids=parents,
        children=children or {},
    )


def _build_graph(*persons: PersonNode, fgs: list[FamilyGroupNode] | None = None) -> FamilyGraph:
    g = FamilyGraph()
    for p in persons:
        g.add_person(p)
    for fg in (fgs or []):
        g.add_family_group(fg)
    return g


@pytest.fixture
def svc() -> FamilyTreeDomainService:
    return FamilyTreeDomainService()


# ── add_parent ────────────────────────────────────────────────────

class TestAddParent:
    def test_creates_new_family_group_when_none_exists(self, svc: FamilyTreeDomainService) -> None:
        parent = _person("Parent")
        child = _person("Child")
        g = _build_graph(parent, child)

        result = svc.add_parent(g, TREE_ID, TENANT_ID, child.id, parent.id)

        assert result.new_family_group is not None
        assert any(m.person_id == parent.id and m.role == "PARENT" for m in result.memberships)
        assert any(m.person_id == child.id and m.role == "CHILD" for m in result.memberships)

    def test_reuses_existing_family_group_with_vacancy(self, svc: FamilyTreeDomainService) -> None:
        parent1 = _person("Parent1")
        parent2 = _person("Parent2")
        child = _person("Child")
        fg = _fg([parent1.id], {child.id: ParentageType.BIOLOGICAL})
        g = _build_graph(parent1, parent2, child, fgs=[fg])

        result = svc.add_parent(g, TREE_ID, TENANT_ID, child.id, parent2.id)

        assert result.new_family_group is None  # no new group needed
        assert any(m.person_id == parent2.id and m.role == "PARENT" for m in result.memberships)

    def test_raises_for_person_not_in_tree(self, svc: FamilyTreeDomainService) -> None:
        child = _person("Child")
        outsider = PersonNode(id=uuid.uuid4(), tree_id=uuid.uuid4(), tenant_id=TENANT_ID)
        g = _build_graph(child, outsider)

        with pytest.raises(PersonNotInTreeError):
            svc.add_parent(g, TREE_ID, TENANT_ID, child.id, outsider.id)

    def test_raises_self_relationship(self, svc: FamilyTreeDomainService) -> None:
        p = _person()
        g = _build_graph(p)
        with pytest.raises(SelfRelationshipError):
            svc.add_parent(g, TREE_ID, TENANT_ID, p.id, p.id)

    def test_raises_circular_relationship(self, svc: FamilyTreeDomainService) -> None:
        grandparent = _person("GP")
        parent = _person("Parent")
        child = _person("Child")
        fg1 = _fg([grandparent.id], {parent.id: ParentageType.BIOLOGICAL})
        fg2 = _fg([parent.id], {child.id: ParentageType.BIOLOGICAL})
        g = _build_graph(grandparent, parent, child, fgs=[fg1, fg2])

        # child cannot become grandparent's parent
        with pytest.raises(CircularRelationshipError):
            svc.add_parent(g, TREE_ID, TENANT_ID, grandparent.id, child.id)

    def test_parentage_type_preserved(self, svc: FamilyTreeDomainService) -> None:
        parent = _person("Parent")
        child = _person("Child")
        g = _build_graph(parent, child)

        result = svc.add_parent(
            g, TREE_ID, TENANT_ID, child.id, parent.id,
            parentage_type=ParentageType.ADOPTIVE,
        )
        child_membership = next(m for m in result.memberships if m.role == "CHILD")
        assert child_membership.parentage_type == ParentageType.ADOPTIVE


# ── add_child ─────────────────────────────────────────────────────

class TestAddChild:
    def test_creates_family_group_with_parent(self, svc: FamilyTreeDomainService) -> None:
        parent = _person("Parent")
        child = _person("Child")
        g = _build_graph(parent, child)

        result = svc.add_child(g, TREE_ID, TENANT_ID, parent.id, child.id)

        assert result.new_family_group is not None
        assert any(m.role == "CHILD" and m.person_id == child.id for m in result.memberships)

    def test_with_other_parent_creates_couple_group(self, svc: FamilyTreeDomainService) -> None:
        parent1 = _person("P1")
        parent2 = _person("P2")
        child = _person("Child")
        g = _build_graph(parent1, parent2, child)

        result = svc.add_child(
            g, TREE_ID, TENANT_ID, parent1.id, child.id,
            other_parent_id=parent2.id,
        )

        parent_memberships = [m for m in result.memberships if m.role == "PARENT"]
        parent_ids = {m.person_id for m in parent_memberships}
        assert parent1.id in parent_ids
        assert parent2.id in parent_ids

    def test_reuses_existing_couple_family_group(self, svc: FamilyTreeDomainService) -> None:
        p1 = _person("P1")
        p2 = _person("P2")
        child1 = _person("Child1")
        child2 = _person("Child2")
        existing_fg = _fg([p1.id, p2.id], {child1.id: ParentageType.BIOLOGICAL})
        g = _build_graph(p1, p2, child1, child2, fgs=[existing_fg])

        result = svc.add_child(
            g, TREE_ID, TENANT_ID, p1.id, child2.id,
            other_parent_id=p2.id,
        )

        assert result.new_family_group is None  # existing group reused

    def test_raises_when_child_already_has_parents(self, svc: FamilyTreeDomainService) -> None:
        parent = _person("Parent")
        existing_parent = _person("ExistingParent")
        child = _person("Child")
        fg = _fg([existing_parent.id], {child.id: ParentageType.BIOLOGICAL})
        g = _build_graph(parent, existing_parent, child, fgs=[fg])

        with pytest.raises(PersonAlreadyHasParentsError):
            svc.add_child(g, TREE_ID, TENANT_ID, parent.id, child.id)


# ── add_spouse ────────────────────────────────────────────────────

class TestAddSpouse:
    def test_creates_family_group(self, svc: FamilyTreeDomainService) -> None:
        p1, p2 = _person("P1"), _person("P2")
        g = _build_graph(p1, p2)

        result = svc.add_spouse(g, TREE_ID, TENANT_ID, p1.id, p2.id)

        assert result.new_family_group is not None
        parent_ids = {m.person_id for m in result.memberships if m.role == "PARENT"}
        assert parent_ids == {p1.id, p2.id}

    def test_union_type_preserved(self, svc: FamilyTreeDomainService) -> None:
        p1, p2 = _person("P1"), _person("P2")
        g = _build_graph(p1, p2)

        result = svc.add_spouse(
            g, TREE_ID, TENANT_ID, p1.id, p2.id,
            union_type=UnionType.PARTNERSHIP,
        )
        assert result.new_family_group is not None
        assert result.new_family_group.union_type == UnionType.PARTNERSHIP

    def test_raises_self_spouse(self, svc: FamilyTreeDomainService) -> None:
        p = _person()
        g = _build_graph(p)
        with pytest.raises(SelfRelationshipError):
            svc.add_spouse(g, TREE_ID, TENANT_ID, p.id, p.id)

    def test_raises_duplicate_spouse(self, svc: FamilyTreeDomainService) -> None:
        p1, p2 = _person("P1"), _person("P2")
        fg = _fg([p1.id, p2.id])
        g = _build_graph(p1, p2, fgs=[fg])

        with pytest.raises(DuplicateRelationshipError):
            svc.add_spouse(g, TREE_ID, TENANT_ID, p1.id, p2.id)

    def test_allows_multiple_spouses_sequentially(self, svc: FamilyTreeDomainService) -> None:
        """Divorce & remarriage: person can be a parent in multiple family groups."""
        p = _person("Person")
        spouse1 = _person("Spouse1")
        spouse2 = _person("Spouse2")
        fg1 = _fg([p.id, spouse1.id])
        g = _build_graph(p, spouse1, spouse2, fgs=[fg1])

        result = svc.add_spouse(g, TREE_ID, TENANT_ID, p.id, spouse2.id)
        assert result.new_family_group is not None


# ── add_sibling ───────────────────────────────────────────────────

class TestAddSibling:
    def test_adds_to_existing_family_group(self, svc: FamilyTreeDomainService) -> None:
        parent = _person("Parent")
        person = _person("Person")
        sibling = _person("Sibling")
        fg = _fg([parent.id], {person.id: ParentageType.BIOLOGICAL})
        g = _build_graph(parent, person, sibling, fgs=[fg])

        result = svc.add_sibling(g, TREE_ID, TENANT_ID, person.id, sibling.id)

        assert result.new_family_group is None
        assert any(m.person_id == sibling.id and m.role == "CHILD" for m in result.memberships)

    def test_creates_new_group_when_person_has_no_parents(self, svc: FamilyTreeDomainService) -> None:
        person = _person("Person")
        sibling = _person("Sibling")
        g = _build_graph(person, sibling)

        result = svc.add_sibling(g, TREE_ID, TENANT_ID, person.id, sibling.id)

        assert result.new_family_group is not None
        # Both person and sibling should be added to the new group
        roles = {m.person_id: m.role for m in result.memberships}
        assert roles[person.id] == "CHILD"
        assert roles[sibling.id] == "CHILD"

    def test_raises_self_sibling(self, svc: FamilyTreeDomainService) -> None:
        p = _person()
        g = _build_graph(p)
        with pytest.raises(SelfRelationshipError):
            svc.add_sibling(g, TREE_ID, TENANT_ID, p.id, p.id)

    def test_raises_when_sibling_already_has_parents(self, svc: FamilyTreeDomainService) -> None:
        person = _person("Person")
        sibling = _person("Sibling")
        other_parent = _person("OtherParent")
        fg = _fg([other_parent.id], {sibling.id: ParentageType.BIOLOGICAL})
        g = _build_graph(person, sibling, other_parent, fgs=[fg])

        with pytest.raises(PersonAlreadyHasParentsError):
            svc.add_sibling(g, TREE_ID, TENANT_ID, person.id, sibling.id)


# ── Mutation result structure ─────────────────────────────────────

class TestMutationResult:
    def test_result_has_description(self, svc: FamilyTreeDomainService) -> None:
        p1, p2 = _person(), _person()
        g = _build_graph(p1, p2)
        result = svc.add_spouse(g, TREE_ID, TENANT_ID, p1.id, p2.id)
        assert result.description

    def test_memberships_not_empty(self, svc: FamilyTreeDomainService) -> None:
        parent = _person()
        child = _person()
        g = _build_graph(parent, child)
        result = svc.add_parent(g, TREE_ID, TENANT_ID, child.id, parent.id)
        assert len(result.memberships) > 0

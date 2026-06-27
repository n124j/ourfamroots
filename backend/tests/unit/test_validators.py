"""Unit tests for genealogy validators — especially circular relationship detection."""

from __future__ import annotations

import uuid
import pytest

from src.domain.genealogy.entities import FamilyGroupNode, ParentageType, PersonNode
from src.domain.genealogy.exceptions import (
    CircularRelationshipError,
    DuplicateRelationshipError,
    FamilyGroupFullError,
    PersonAlreadyHasParentsError,
    SelfRelationshipError,
)
from src.domain.genealogy.graph import FamilyGraph
from src.domain.genealogy.validators import (
    CircularRelationshipValidator,
    CompositeValidator,
    RelationshipIntegrityValidator,
)


# ── Helpers ───────────────────────────────────────────────────────

def _person(name: str = "P") -> PersonNode:
    return PersonNode(id=uuid.uuid4(), tree_id=uuid.uuid4(), tenant_id=uuid.uuid4(),
                      display_given_name=name)


def _fg(parents: list[uuid.UUID], children: dict | None = None) -> FamilyGroupNode:
    return FamilyGroupNode(
        id=uuid.uuid4(), tree_id=uuid.uuid4(), tenant_id=uuid.uuid4(),
        parent_ids=parents, children=children or {},
    )


def _linear_graph(n: int) -> tuple[FamilyGraph, list[PersonNode]]:
    """Build a linear chain: p[0] → p[1] → … → p[n-1]"""
    g = FamilyGraph()
    persons = [_person(f"P{i}") for i in range(n)]
    for p in persons:
        g.add_person(p)
    for i in range(n - 1):
        fg = _fg([persons[i].id], {persons[i + 1].id: ParentageType.BIOLOGICAL})
        g.add_family_group(fg)
    return g, persons


# ── CircularRelationshipValidator ─────────────────────────────────

class TestCircularRelationshipValidator:
    def setup_method(self) -> None:
        self.v = CircularRelationshipValidator()

    def test_no_error_for_unrelated_persons(self) -> None:
        g, ps = _linear_graph(3)
        # Adding a brand-new parent to ps[0] — ps[0] has no parents yet
        new_parent = _person("NewParent")
        g.add_person(new_parent)
        # Should not raise
        self.v.validate_add_parent(g, child_id=ps[0].id, parent_id=new_parent.id)

    def test_raises_when_parent_is_descendant(self) -> None:
        """grandchild cannot become grandparent's parent."""
        g, ps = _linear_graph(3)
        # ps[0] → ps[1] → ps[2]
        # Trying to make ps[2] the parent of ps[0] → circular
        with pytest.raises(CircularRelationshipError):
            self.v.validate_add_parent(g, child_id=ps[0].id, parent_id=ps[2].id)

    def test_raises_when_child_is_ancestor(self) -> None:
        """Cannot make an ancestor a child of their own descendant."""
        g, ps = _linear_graph(4)
        # ps[0] → ps[1] → ps[2] → ps[3]
        # Trying to make ps[3] parent of ps[0] → circular
        with pytest.raises(CircularRelationshipError):
            self.v.validate_add_parent(g, child_id=ps[0].id, parent_id=ps[3].id)

    def test_no_false_positive_for_parallel_branch(self) -> None:
        """Two unrelated branches should not trigger cycle detection."""
        g, branch1 = _linear_graph(3)
        _, branch2 = _linear_graph(3)
        for p in branch2:
            g.add_person(p)
        # Adding branch2[0] as parent of branch1[0] — no cycle
        self.v.validate_add_parent(g, child_id=branch1[0].id, parent_id=branch2[0].id)

    def test_deep_chain_detected(self) -> None:
        """Cycle should be caught even 10 levels deep."""
        g, ps = _linear_graph(10)
        with pytest.raises(CircularRelationshipError):
            self.v.validate_add_parent(g, child_id=ps[0].id, parent_id=ps[9].id)

    def test_self_as_parent_not_caught_here(self) -> None:
        """Self-relationship is caught by RelationshipIntegrityValidator, not circular."""
        g, ps = _linear_graph(2)
        # ps[0] has no descendants so circular check passes —
        # self-relationship check is a separate concern
        self.v.validate_add_parent(g, child_id=ps[0].id, parent_id=ps[0].id)


# ── RelationshipIntegrityValidator ────────────────────────────────

class TestIntegrityValidator:
    def setup_method(self) -> None:
        self.v = RelationshipIntegrityValidator()

    def test_self_relationship_raises(self) -> None:
        pid = uuid.uuid4()
        with pytest.raises(SelfRelationshipError):
            self.v.validate_not_self(pid, pid, "parent")

    def test_different_persons_ok(self) -> None:
        self.v.validate_not_self(uuid.uuid4(), uuid.uuid4(), "parent")

    def test_person_with_existing_parents_raises(self) -> None:
        p = _person()
        fg = _fg([], {p.id: ParentageType.BIOLOGICAL})
        g = FamilyGraph()
        g.add_person(p)
        g.add_family_group(fg)

        with pytest.raises(PersonAlreadyHasParentsError):
            self.v.validate_child_has_no_parents(g, p.id)

    def test_person_without_parents_ok(self) -> None:
        p = _person()
        g = FamilyGraph()
        g.add_person(p)
        self.v.validate_child_has_no_parents(g, p.id)

    def test_family_group_full_raises(self) -> None:
        p1, p2 = _person(), _person()
        fg = _fg([p1.id, p2.id])
        g = FamilyGraph()
        g.add_person(p1)
        g.add_person(p2)
        g.add_family_group(fg)

        with pytest.raises(FamilyGroupFullError):
            self.v.validate_family_group_not_full(g, fg.id)

    def test_family_group_with_one_parent_not_full(self) -> None:
        p = _person()
        fg = _fg([p.id])
        g = FamilyGraph()
        g.add_person(p)
        g.add_family_group(fg)
        self.v.validate_family_group_not_full(g, fg.id)  # should not raise

    def test_duplicate_parent_raises(self) -> None:
        p = _person()
        fg = _fg([p.id])
        g = FamilyGraph()
        g.add_person(p)
        g.add_family_group(fg)

        with pytest.raises(DuplicateRelationshipError):
            self.v.validate_not_duplicate_parent(g, fg.id, p.id)

    def test_duplicate_spouse_raises(self) -> None:
        p1, p2 = _person(), _person()
        fg = _fg([p1.id, p2.id])
        g = FamilyGraph()
        g.add_person(p1)
        g.add_person(p2)
        g.add_family_group(fg)

        with pytest.raises(DuplicateRelationshipError):
            self.v.validate_not_duplicate_spouse(g, p1.id, p2.id)


# ── CompositeValidator ────────────────────────────────────────────

class TestCompositeValidator:
    def setup_method(self) -> None:
        self.v = CompositeValidator()

    def test_add_parent_self_raises(self) -> None:
        g = FamilyGraph()
        pid = uuid.uuid4()
        with pytest.raises(SelfRelationshipError):
            self.v.before_add_parent(g, pid, pid, uuid.uuid4())

    def test_add_parent_circular_raises(self) -> None:
        g, ps = _linear_graph(3)
        with pytest.raises(CircularRelationshipError):
            self.v.before_add_parent(g, ps[0].id, ps[2].id, uuid.uuid4())

    def test_add_child_when_child_has_parents_raises(self) -> None:
        p = _person("Parent")
        child = _person("Child")
        fg = _fg([], {child.id: ParentageType.BIOLOGICAL})
        g = FamilyGraph()
        g.add_person(p)
        g.add_person(child)
        g.add_family_group(fg)

        with pytest.raises(PersonAlreadyHasParentsError):
            self.v.before_add_child(g, child.id, p.id, fg.id)

    def test_add_spouse_self_raises(self) -> None:
        pid = uuid.uuid4()
        g = FamilyGraph()
        with pytest.raises(SelfRelationshipError):
            self.v.before_add_spouse(g, pid, pid)

    def test_add_spouse_duplicate_raises(self) -> None:
        p1, p2 = _person(), _person()
        fg = _fg([p1.id, p2.id])
        g = FamilyGraph()
        g.add_person(p1)
        g.add_person(p2)
        g.add_family_group(fg)

        with pytest.raises(DuplicateRelationshipError):
            self.v.before_add_spouse(g, p1.id, p2.id)

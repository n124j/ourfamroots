"""Genealogy integrity validators.

All validators operate on FamilyGraph (in-memory) and raise domain
exceptions. They are called by FamilyTreeDomainService *before* any
DB write, so invalid data never reaches the database.

Key invariants enforced here
─────────────────────────────
1. No self-relationships (a person cannot be their own parent/child/spouse).
2. No circular ancestry: a proposed parent must not already be a descendant
   of the proposed child (which would mean the child is an ancestor of their
   own parent — impossible in biology and confusing in records).
3. A person can belong to at most one family group as a CHILD.
4. A family group supports at most two parents.
5. Duplicate parent/child assignments are rejected.
"""

from __future__ import annotations

import uuid

from src.domain.genealogy.entities import ParentageType, Sex
from src.domain.genealogy.exceptions import (
    BiologicalParentSexError,
    CircularRelationshipError,
    DuplicateRelationshipError,
    FamilyGroupFullError,
    PersonAlreadyHasParentsError,
    SelfRelationshipError,
)
from src.domain.genealogy.graph import FamilyGraph


class CircularRelationshipValidator:
    """
    Detects ancestry loops before a parent-child edge is committed.

    Algorithm (O(n) in ancestors of child):
        1. Check proposed_parent is not already a descendant of proposed_child.
           If so → circular: child would become ancestor of their own parent.
        2. Equivalently: ensure proposed_child is not an ancestor of proposed_parent.

    We use the graph's descendants_flat() (BFS downward from proposed_child).
    If proposed_parent appears in that set → loop.
    """

    def validate_add_parent(
        self,
        graph: FamilyGraph,
        child_id: uuid.UUID,
        parent_id: uuid.UUID,
    ) -> None:
        """
        Raise CircularRelationshipError if adding parent_id as a parent of
        child_id would create an ancestry loop.
        """
        # Descendants of child_id include child_id itself after traversal,
        # but we start BFS from child_id so we need to check if parent_id
        # is reachable going *down* from child_id.
        descendants = graph.all_descendants(child_id)
        if parent_id in descendants:
            raise CircularRelationshipError(
                ancestor_id=child_id,
                descendant_id=parent_id,
            )

        # Also check the other direction: child must not already be an
        # ancestor of the proposed parent (handles disconnected sub-graphs
        # that will be joined by this edge).
        ancestors_of_parent = graph.all_ancestors(parent_id)
        if child_id in ancestors_of_parent:
            raise CircularRelationshipError(
                ancestor_id=child_id,
                descendant_id=parent_id,
            )


class RelationshipIntegrityValidator:
    """Validates structural constraints (not loop detection)."""

    def validate_not_self(
        self,
        person1_id: uuid.UUID,
        person2_id: uuid.UUID,
        relation: str,
    ) -> None:
        if person1_id == person2_id:
            raise SelfRelationshipError(person_id=person1_id, relation=relation)

    def validate_child_has_no_parents(
        self,
        graph: FamilyGraph,
        child_id: uuid.UUID,
    ) -> None:
        """A person can only be a child in one family group."""
        existing_fg = graph.family_group_as_child(child_id)
        if existing_fg is not None:
            raise PersonAlreadyHasParentsError(
                person_id=child_id,
                family_group_id=existing_fg.id,
            )

    def validate_family_group_not_full(
        self,
        graph: FamilyGraph,
        fg_id: uuid.UUID,
    ) -> None:
        fg = graph.get_family_group(fg_id)
        if fg is not None and fg.is_full():
            raise FamilyGroupFullError(family_group_id=fg_id)

    def validate_not_duplicate_parent(
        self,
        graph: FamilyGraph,
        fg_id: uuid.UUID,
        parent_id: uuid.UUID,
    ) -> None:
        fg = graph.get_family_group(fg_id)
        if fg is not None and fg.has_parent(parent_id):
            raise DuplicateRelationshipError(
                person1_id=parent_id,
                person2_id=fg_id,
                relation="parent-in-family-group",
            )

    def validate_not_duplicate_child(
        self,
        graph: FamilyGraph,
        fg_id: uuid.UUID,
        child_id: uuid.UUID,
    ) -> None:
        fg = graph.get_family_group(fg_id)
        if fg is not None and fg.has_child(child_id):
            raise DuplicateRelationshipError(
                person1_id=child_id,
                person2_id=fg_id,
                relation="child-in-family-group",
            )

    def validate_biological_parent_sex(
        self,
        graph: FamilyGraph,
        parent_ids: list[uuid.UUID],
        parentage_type: ParentageType,
    ) -> None:
        """Two parents of the same sex cannot have a BIOLOGICAL child."""
        if parentage_type != ParentageType.BIOLOGICAL:
            return
        if len(parent_ids) < 2:
            return
        sexes = []
        for pid in parent_ids:
            p = graph.get_person(pid)
            if p is not None and p.sex not in (Sex.UNKNOWN, Sex.OTHER):
                sexes.append(p.sex)
        if len(sexes) >= 2 and len(set(sexes)) == 1:
            raise BiologicalParentSexError(sexes[0].value)

    def validate_not_duplicate_spouse(
        self,
        graph: FamilyGraph,
        person1_id: uuid.UUID,
        person2_id: uuid.UUID,
    ) -> None:
        """Ensure no existing family group already pairs these two as parents."""
        for fg in graph.family_groups_as_parent(person1_id):
            if person2_id in fg.parent_ids:
                raise DuplicateRelationshipError(
                    person1_id=person1_id,
                    person2_id=person2_id,
                    relation="spouse",
                )


class CompositeValidator:
    """
    Convenience wrapper that runs all validators in the correct sequence.
    Instantiated once and reused by FamilyTreeDomainService.
    """

    def __init__(self) -> None:
        self._circular = CircularRelationshipValidator()
        self._integrity = RelationshipIntegrityValidator()

    def before_add_parent(
        self,
        graph: FamilyGraph,
        child_id: uuid.UUID,
        parent_id: uuid.UUID,
        fg_id: uuid.UUID,
        parentage_type: ParentageType = ParentageType.BIOLOGICAL,
    ) -> None:
        self._integrity.validate_not_self(child_id, parent_id, "parent")
        self._integrity.validate_not_duplicate_parent(graph, fg_id, parent_id)
        self._circular.validate_add_parent(graph, child_id, parent_id)
        fg = graph.get_family_group(fg_id)
        if fg is not None:
            all_parents = list(fg.parent_ids) + [parent_id]
            self._integrity.validate_biological_parent_sex(graph, all_parents, parentage_type)

    def before_add_child(
        self,
        graph: FamilyGraph,
        child_id: uuid.UUID,
        parent_id: uuid.UUID,
        fg_id: uuid.UUID,
        parentage_type: ParentageType = ParentageType.BIOLOGICAL,
    ) -> None:
        self._integrity.validate_not_self(child_id, parent_id, "child")
        self._integrity.validate_child_has_no_parents(graph, child_id)
        self._integrity.validate_not_duplicate_child(graph, fg_id, child_id)
        self._circular.validate_add_parent(graph, child_id, parent_id)
        fg = graph.get_family_group(fg_id)
        if fg is not None:
            self._integrity.validate_biological_parent_sex(graph, fg.parent_ids, parentage_type)

    def before_add_spouse(
        self,
        graph: FamilyGraph,
        person1_id: uuid.UUID,
        person2_id: uuid.UUID,
    ) -> None:
        self._integrity.validate_not_self(person1_id, person2_id, "spouse")
        self._integrity.validate_not_duplicate_spouse(graph, person1_id, person2_id)

    def before_add_both_parents(
        self,
        graph: FamilyGraph,
        child_id: uuid.UUID,
        father_id: uuid.UUID,
        mother_id: uuid.UUID,
        fg_id: uuid.UUID,
        fg_exists: bool,
        parentage_type: ParentageType = ParentageType.BIOLOGICAL,
    ) -> None:
        self._integrity.validate_not_self(child_id, father_id, "parent")
        self._integrity.validate_not_self(child_id, mother_id, "parent")
        if not fg_exists:
            self._integrity.validate_not_duplicate_parent(graph, fg_id, father_id)
            self._integrity.validate_not_duplicate_parent(graph, fg_id, mother_id)
        self._integrity.validate_child_has_no_parents(graph, child_id)
        self._integrity.validate_not_duplicate_child(graph, fg_id, child_id)
        self._circular.validate_add_parent(graph, child_id, father_id)
        self._circular.validate_add_parent(graph, child_id, mother_id)
        self._integrity.validate_biological_parent_sex(graph, [father_id, mother_id], parentage_type)

    def before_add_sibling(
        self,
        graph: FamilyGraph,
        person_id: uuid.UUID,
        sibling_id: uuid.UUID,
    ) -> None:
        self._integrity.validate_not_self(person_id, sibling_id, "sibling")
        # Sibling is implemented as: add sibling_id as a child to the same
        # family group as person_id. So sibling_id must not already have parents.
        self._integrity.validate_child_has_no_parents(graph, sibling_id)

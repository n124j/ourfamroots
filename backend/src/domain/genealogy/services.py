"""FamilyTreeDomainService — pure domain logic for mutating a family tree.

This service operates entirely on FamilyGraph + domain entities. It has no
database dependency: the application service (application/genealogy/service.py)
loads the graph from DB, calls these methods to get the mutation result, then
persists the changes.

Each "add_*" method returns a MutationResult describing what should be
written to the database. The application service translates this into
actual repository calls.

Design choices
──────────────
• Validate → mutate in-memory graph → return commands (not DB calls)
• Methods are synchronous — all I/O happens outside this layer
• The graph passed in is treated as read-only; a working copy is made
  internally for cycle detection when the validation requires traversal
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from src.domain.genealogy.calculators import classify_kinship, lineage_paths
from src.domain.genealogy.entities import (
    FamilyGroupNode,
    KinshipResult,
    LineagePath,
    ParentageType,
    UnionType,
)
from src.domain.genealogy.exceptions import (
    NoRelationshipPathError,
    PersonNotInTreeError,
)
from src.domain.genealogy.graph import FamilyGraph
from src.domain.genealogy.validators import CompositeValidator


# ── Mutation commands (returned to the application layer) ─────────

@dataclass
class AddPersonToFamilyGroupCommand:
    """Instruct the repo to add a person to a family group."""
    family_group_id: uuid.UUID
    person_id: uuid.UUID
    tree_id: uuid.UUID
    role: str                       # "PARENT" | "CHILD"
    parentage_type: ParentageType = ParentageType.BIOLOGICAL


@dataclass
class CreateFamilyGroupCommand:
    """Instruct the repo to create a new family group."""
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    tree_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    union_type: UnionType = UnionType.UNKNOWN


@dataclass
class MutationResult:
    """
    The outcome of a successful domain mutation.
    Contains zero or more commands the application layer should execute.
    """
    new_family_group: Optional[CreateFamilyGroupCommand] = None
    memberships: list[AddPersonToFamilyGroupCommand] = field(default_factory=list)
    # Human-readable summary for logging
    description: str = ""


# ── Domain service ────────────────────────────────────────────────

class FamilyTreeDomainService:
    """
    Orchestrates all family tree mutations.

    Usage (in the application layer):
        graph = await graph_loader.load(tree_id, tenant_id)
        result = domain_svc.add_parent(graph, child_id, parent_id, ...)
        await repo.apply_mutation(result)
    """

    def __init__(self) -> None:
        self._validator = CompositeValidator()

    # ── Guard: ensure person belongs to tree ──────────────────────

    def _require_in_tree(
        self,
        graph: FamilyGraph,
        person_id: uuid.UUID,
        tree_id: uuid.UUID,
    ) -> None:
        person = graph.get_person(person_id)
        if person is None or person.tree_id != tree_id:
            raise PersonNotInTreeError(person_id=person_id, tree_id=tree_id)

    # ── Add parent ────────────────────────────────────────────────

    def add_parent(
        self,
        graph: FamilyGraph,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        child_id: uuid.UUID,
        parent_id: uuid.UUID,
        parentage_type: ParentageType = ParentageType.BIOLOGICAL,
        union_type: UnionType = UnionType.UNKNOWN,
    ) -> MutationResult:
        """
        Add parent_id as a parent of child_id.

        If child_id already has a family-of-origin group with a vacant parent
        slot, the new parent is added to that group. Otherwise a new family
        group is created.

        Validation: self-relationship, duplicate, circular ancestry.
        """
        self._require_in_tree(graph, child_id, tree_id)
        self._require_in_tree(graph, parent_id, tree_id)

        existing_fg = graph.family_group_as_child(child_id)

        if existing_fg is not None and not existing_fg.is_full():
            # Add to the existing family group
            fg_id = existing_fg.id
        else:
            # Will create a new family group (or existing is full → error handled by validator)
            fg_id = uuid.uuid4()
            existing_fg = None  # signal: create new

        self._validator.before_add_parent(graph, child_id, parent_id, fg_id, parentage_type)

        result = MutationResult(
            description=f"Add parent {parent_id} to child {child_id}",
        )

        if existing_fg is None:
            # Need a new family group
            result.new_family_group = CreateFamilyGroupCommand(
                id=fg_id,
                tree_id=tree_id,
                tenant_id=tenant_id,
                union_type=union_type,
            )
            # Also link child to the new group
            result.memberships.append(AddPersonToFamilyGroupCommand(
                family_group_id=fg_id,
                person_id=child_id,
                tree_id=tree_id,
                role="CHILD",
                parentage_type=parentage_type,
            ))

        result.memberships.append(AddPersonToFamilyGroupCommand(
            family_group_id=fg_id,
            person_id=parent_id,
            tree_id=tree_id,
            role="PARENT",
        ))

        return result

    # ── Add child ─────────────────────────────────────────────────

    def add_child(
        self,
        graph: FamilyGraph,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        parent_id: uuid.UUID,
        child_id: uuid.UUID,
        other_parent_id: Optional[uuid.UUID] = None,
        parentage_type: ParentageType = ParentageType.BIOLOGICAL,
        union_type: UnionType = UnionType.UNKNOWN,
    ) -> MutationResult:
        """
        Add child_id as a child of parent_id (and optionally other_parent_id).

        Finds the appropriate family group:
        - If parent_id and other_parent_id already share a family group → use it.
        - Otherwise create a new one.
        """
        self._require_in_tree(graph, parent_id, tree_id)
        self._require_in_tree(graph, child_id, tree_id)
        if other_parent_id is not None:
            self._require_in_tree(graph, other_parent_id, tree_id)

        # Find or decide family group
        fg_id, fg_exists = self._find_or_plan_family_group(
            graph, parent_id, other_parent_id
        )

        self._validator.before_add_child(graph, child_id, parent_id, fg_id, parentage_type)

        result = MutationResult(
            description=f"Add child {child_id} to parent {parent_id}",
        )

        if not fg_exists:
            result.new_family_group = CreateFamilyGroupCommand(
                id=fg_id,
                tree_id=tree_id,
                tenant_id=tenant_id,
                union_type=union_type,
            )
            result.memberships.append(AddPersonToFamilyGroupCommand(
                family_group_id=fg_id,
                person_id=parent_id,
                tree_id=tree_id,
                role="PARENT",
            ))
            if other_parent_id is not None:
                result.memberships.append(AddPersonToFamilyGroupCommand(
                    family_group_id=fg_id,
                    person_id=other_parent_id,
                    tree_id=tree_id,
                    role="PARENT",
                ))

        result.memberships.append(AddPersonToFamilyGroupCommand(
            family_group_id=fg_id,
            person_id=child_id,
            tree_id=tree_id,
            role="CHILD",
            parentage_type=parentage_type,
        ))

        return result

    # ── Add both parents ─────────────────────────────────────────

    def add_both_parents(
        self,
        graph: FamilyGraph,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        child_id: uuid.UUID,
        father_id: uuid.UUID,
        mother_id: uuid.UUID,
        parentage_type: ParentageType = ParentageType.BIOLOGICAL,
        union_type: UnionType = UnionType.MARRIAGE,
    ) -> MutationResult:
        """
        Add a father and mother to a child in one atomic operation.

        If father and mother already share a family group, the child is added
        to that group (becoming a sibling of their existing children).
        Otherwise a new family group is created for all three.
        """
        self._require_in_tree(graph, child_id, tree_id)
        self._require_in_tree(graph, father_id, tree_id)
        self._require_in_tree(graph, mother_id, tree_id)

        fg_id, fg_exists = self._find_or_plan_family_group(graph, father_id, mother_id)

        self._validator.before_add_both_parents(
            graph, child_id, father_id, mother_id, fg_id, fg_exists, parentage_type
        )

        result = MutationResult(
            description=f"Add both parents (father={father_id}, mother={mother_id}) to child {child_id}",
        )

        if not fg_exists:
            result.new_family_group = CreateFamilyGroupCommand(
                id=fg_id,
                tree_id=tree_id,
                tenant_id=tenant_id,
                union_type=union_type,
            )
            result.memberships.append(AddPersonToFamilyGroupCommand(
                family_group_id=fg_id, person_id=father_id, tree_id=tree_id, role="PARENT",
            ))
            result.memberships.append(AddPersonToFamilyGroupCommand(
                family_group_id=fg_id, person_id=mother_id, tree_id=tree_id, role="PARENT",
            ))

        result.memberships.append(AddPersonToFamilyGroupCommand(
            family_group_id=fg_id,
            person_id=child_id,
            tree_id=tree_id,
            role="CHILD",
            parentage_type=parentage_type,
        ))

        return result

    # ── Add spouse ────────────────────────────────────────────────

    def add_spouse(
        self,
        graph: FamilyGraph,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        person1_id: uuid.UUID,
        person2_id: uuid.UUID,
        union_type: UnionType = UnionType.MARRIAGE,
    ) -> MutationResult:
        """
        Create a new family group pairing person1 and person2 as co-parents
        (without any children yet). Children can be added later via add_child.
        """
        self._require_in_tree(graph, person1_id, tree_id)
        self._require_in_tree(graph, person2_id, tree_id)

        self._validator.before_add_spouse(graph, person1_id, person2_id)

        fg_id = uuid.uuid4()
        return MutationResult(
            description=f"Add spouse relationship between {person1_id} and {person2_id}",
            new_family_group=CreateFamilyGroupCommand(
                id=fg_id,
                tree_id=tree_id,
                tenant_id=tenant_id,
                union_type=union_type,
            ),
            memberships=[
                AddPersonToFamilyGroupCommand(
                    family_group_id=fg_id, person_id=person1_id, tree_id=tree_id, role="PARENT"
                ),
                AddPersonToFamilyGroupCommand(
                    family_group_id=fg_id, person_id=person2_id, tree_id=tree_id, role="PARENT"
                ),
            ],
        )

    # ── Add sibling ───────────────────────────────────────────────

    def add_sibling(
        self,
        graph: FamilyGraph,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        person_id: uuid.UUID,
        sibling_id: uuid.UUID,
        parentage_type: ParentageType = ParentageType.BIOLOGICAL,
    ) -> MutationResult:
        """
        Add sibling_id as a sibling of person_id.

        If person_id already has a family-of-origin group, sibling_id is
        added as another child of the same group. If not, a new family group
        is created (with no parents recorded yet).
        """
        self._require_in_tree(graph, person_id, tree_id)
        self._require_in_tree(graph, sibling_id, tree_id)

        self._validator.before_add_sibling(graph, person_id, sibling_id)

        existing_fg = graph.family_group_as_child(person_id)

        result = MutationResult(
            description=f"Add sibling {sibling_id} to {person_id}",
        )

        if existing_fg is not None:
            fg_id = existing_fg.id
        else:
            fg_id = uuid.uuid4()
            result.new_family_group = CreateFamilyGroupCommand(
                id=fg_id,
                tree_id=tree_id,
                tenant_id=tenant_id,
            )
            # Also register person_id in the new group
            result.memberships.append(AddPersonToFamilyGroupCommand(
                family_group_id=fg_id,
                person_id=person_id,
                tree_id=tree_id,
                role="CHILD",
                parentage_type=parentage_type,
            ))

        result.memberships.append(AddPersonToFamilyGroupCommand(
            family_group_id=fg_id,
            person_id=sibling_id,
            tree_id=tree_id,
            role="CHILD",
            parentage_type=parentage_type,
        ))

        return result

    # ── Query methods ─────────────────────────────────────────────

    def kinship(
        self,
        graph: FamilyGraph,
        person1_id: uuid.UUID,
        person2_id: uuid.UUID,
    ) -> KinshipResult:
        return classify_kinship(graph, person1_id, person2_id)

    def get_lineage_paths(
        self,
        graph: FamilyGraph,
        origin: uuid.UUID,
        destination: uuid.UUID,
        max_paths: int = 5,
    ) -> list[LineagePath]:
        paths = lineage_paths(graph, origin, destination, max_paths=max_paths)
        if not paths:
            raise NoRelationshipPathError(origin, destination)
        return paths

    # ── Private helpers ───────────────────────────────────────────

    def _find_or_plan_family_group(
        self,
        graph: FamilyGraph,
        parent1_id: uuid.UUID,
        parent2_id: Optional[uuid.UUID],
    ) -> tuple[uuid.UUID, bool]:
        """
        Look for an existing family group that contains exactly parent1 (and
        optionally parent2). Returns (fg_id, exists_in_graph).
        """
        for fg in graph.family_groups_as_parent(parent1_id):
            if parent2_id is None:
                # Use any family group where parent1 is the sole parent
                if len(fg.parent_ids) == 1:
                    return fg.id, True
            else:
                if parent2_id in fg.parent_ids:
                    return fg.id, True

        return uuid.uuid4(), False

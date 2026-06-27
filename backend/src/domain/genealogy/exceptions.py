"""Genealogy-specific domain exceptions."""
from __future__ import annotations
import uuid
from src.domain.exceptions import ConflictError, DomainError, ValidationError


class CircularRelationshipError(ConflictError):
    def __init__(self, ancestor_id: uuid.UUID, descendant_id: uuid.UUID) -> None:
        super().__init__(
            f"Cannot add: person {descendant_id} is already a descendant of "
            f"{ancestor_id}. This would create a circular ancestry loop."
        )
        self.code = "CIRCULAR_RELATIONSHIP"
        self.ancestor_id = ancestor_id
        self.descendant_id = descendant_id


class PersonAlreadyHasParentsError(ConflictError):
    def __init__(self, person_id: uuid.UUID, family_group_id: uuid.UUID) -> None:
        super().__init__(
            f"Person {person_id} already has a recorded parent family group "
            f"({family_group_id}). Remove the existing parents first."
        )
        self.code = "PERSON_ALREADY_HAS_PARENTS"
        self.person_id = person_id
        self.family_group_id = family_group_id


class FamilyGroupFullError(ConflictError):
    def __init__(self, family_group_id: uuid.UUID) -> None:
        super().__init__(
            f"Family group {family_group_id} already has two parents. "
            "A family group supports a maximum of two parents."
        )
        self.code = "FAMILY_GROUP_FULL"
        self.family_group_id = family_group_id


class SelfRelationshipError(ValidationError):
    def __init__(self, person_id: uuid.UUID, relation: str) -> None:
        super().__init__(
            message=f"A person cannot be their own {relation}.",
            field="person_id",
        )
        self.code = "SELF_RELATIONSHIP"
        self.person_id = person_id


class DuplicateRelationshipError(ConflictError):
    def __init__(self, person1_id: uuid.UUID, person2_id: uuid.UUID, relation: str) -> None:
        super().__init__(
            f"Relationship '{relation}' between {person1_id} and {person2_id} already exists."
        )
        self.code = "DUPLICATE_RELATIONSHIP"


class PersonNotInTreeError(DomainError):
    def __init__(self, person_id: uuid.UUID, tree_id: uuid.UUID) -> None:
        super().__init__(
            message=f"Person {person_id} is not in tree {tree_id}.",
            code="PERSON_NOT_IN_TREE",
        )


class BiologicalParentSexError(ValidationError):
    def __init__(self, sex: str) -> None:
        super().__init__(
            message=(
                f"Two {sex.lower()} parents cannot have a biological child. "
                "Use Adoptive, Step, or Foster instead."
            ),
            field="parentage_type",
        )
        self.code = "BIOLOGICAL_PARENT_SEX"


class NoRelationshipPathError(DomainError):
    def __init__(self, person1_id: uuid.UUID, person2_id: uuid.UUID) -> None:
        super().__init__(
            message=f"No relationship path found between {person1_id} and {person2_id}.",
            code="NO_RELATIONSHIP_PATH",
        )

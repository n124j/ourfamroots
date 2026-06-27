"""Pure domain entities for the genealogy engine.

These are in-memory data objects — they carry no SQLAlchemy machinery and
no I/O. The infrastructure layer is responsible for translating between
ORM models and these entities.

Graph vocabulary
────────────────
  PersonNode       — a single individual
  FamilyGroupNode  — one partnership unit (0-2 parents, N children)
                     analogous to a GEDCOM FAM record
  ParentageType    — how a child relates to the family group
  UnionType        — the nature of the parental partnership
  RelationshipKind — a computed/named relationship between two persons
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


# ── Enumerations ──────────────────────────────────────────────────

class Sex(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class ParentageType(str, Enum):
    BIOLOGICAL = "BIOLOGICAL"
    ADOPTIVE = "ADOPTIVE"
    STEP = "STEP"
    FOSTER = "FOSTER"
    UNKNOWN = "UNKNOWN"


class UnionType(str, Enum):
    MARRIAGE = "MARRIAGE"
    PARTNERSHIP = "PARTNERSHIP"
    COHABITATION = "COHABITATION"
    UNKNOWN = "UNKNOWN"


class RelationshipKind(str, Enum):
    # Direct line
    SELF = "SELF"
    PARENT = "PARENT"
    CHILD = "CHILD"
    GRANDPARENT = "GRANDPARENT"
    GRANDCHILD = "GRANDCHILD"
    GREAT_GRANDPARENT = "GREAT_GRANDPARENT"
    GREAT_GRANDCHILD = "GREAT_GRANDCHILD"
    ANCESTOR = "ANCESTOR"          # > 3 generations up
    DESCENDANT = "DESCENDANT"      # > 3 generations down
    # Siblings
    SIBLING = "SIBLING"            # full sibling (both parents shared)
    HALF_SIBLING = "HALF_SIBLING"  # one parent shared
    STEP_SIBLING = "STEP_SIBLING"  # parent married into
    # Collateral
    AUNT_UNCLE = "AUNT_UNCLE"
    NIECE_NEPHEW = "NIECE_NEPHEW"
    COUSIN = "COUSIN"              # further qualified by degree/removed
    # Partners
    SPOUSE = "SPOUSE"
    # Fallback
    UNKNOWN = "UNKNOWN"


# ── Core domain entities ──────────────────────────────────────────

@dataclass
class PersonNode:
    """Lightweight in-memory representation of a person in the family graph."""

    id: uuid.UUID
    tree_id: uuid.UUID
    tenant_id: uuid.UUID
    display_given_name: str = ""
    display_surname: str = ""
    sex: Sex = Sex.UNKNOWN
    birth_date: Optional[date] = None
    death_date: Optional[date] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    is_living: bool = True
    is_deceased: bool = False
    is_deleted: bool = False
    photo_url: Optional[str] = None
    born_city: Optional[str] = None
    born_country: Optional[str] = None
    died_city: Optional[str] = None
    died_country: Optional[str] = None
    notes: Optional[str] = None

    @property
    def display_name(self) -> str:
        parts = [self.display_given_name, self.display_surname]
        return " ".join(p for p in parts if p) or f"Person({str(self.id)[:8]})"


@dataclass
class FamilyGroupNode:
    """Represents one family unit (partnership + children)."""

    id: uuid.UUID
    tree_id: uuid.UUID
    tenant_id: uuid.UUID
    union_type: UnionType = UnionType.UNKNOWN
    # Ordered list; max 2 elements
    parent_ids: list[uuid.UUID] = field(default_factory=list)
    # child_id → parentage_type
    children: dict[uuid.UUID, ParentageType] = field(default_factory=dict)

    @property
    def child_ids(self) -> list[uuid.UUID]:
        return list(self.children.keys())

    def has_parent(self, person_id: uuid.UUID) -> bool:
        return person_id in self.parent_ids

    def has_child(self, person_id: uuid.UUID) -> bool:
        return person_id in self.children

    def is_full(self) -> bool:
        """A family group supports at most 2 parents."""
        return len(self.parent_ids) >= 2

    def shared_parents(self, other: "FamilyGroupNode") -> list[uuid.UUID]:
        return [p for p in self.parent_ids if p in other.parent_ids]


@dataclass
class KinshipResult:
    """The computed relationship between two persons."""

    person1_id: uuid.UUID
    person2_id: uuid.UUID
    kind: RelationshipKind
    # For cousins: "1st cousin twice removed" etc.
    cousin_degree: Optional[int] = None        # 1 = first cousin, 2 = second, …
    cousin_removed: Optional[int] = None       # 0 = same generation
    # Common ancestors that define the relationship
    common_ancestor_ids: list[uuid.UUID] = field(default_factory=list)
    # Shortest path from person1 → person2 (as person_id hops)
    path: list[uuid.UUID] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.kind == RelationshipKind.COUSIN:
            d = self.cousin_degree or 1
            r = self.cousin_removed or 0
            ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(d, f"{d}th")
            removed_str = f" {r}x removed" if r else ""
            return f"{ordinal} cousin{removed_str}"
        return self.kind.value.replace("_", " ").title()


@dataclass
class LineagePath:
    """A directed path from one person to another through the family graph."""

    nodes: list[uuid.UUID]           # person IDs in order
    # Labels on each step, e.g. ["parent", "parent", "child"]
    edge_labels: list[str] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.nodes) - 1

    @property
    def origin(self) -> uuid.UUID:
        return self.nodes[0]

    @property
    def destination(self) -> uuid.UUID:
        return self.nodes[-1]

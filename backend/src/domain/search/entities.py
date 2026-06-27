"""Search domain value objects and result types."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ── Enumerations ───────────────────────────────────────────────────────────────

class SearchCategory(str, Enum):
    NAME         = "name"          # person name (FTS + trigram)
    RELATIONSHIP = "relationship"  # path between two people
    ANCESTOR     = "ancestor"      # all ancestors of a person
    DESCENDANT   = "descendant"    # all descendants of a person
    BRANCH       = "branch"        # all descendants of a root (alias for DESCENDANT)
    RELATIVE     = "relative"      # all relatives within N hops


class SearchScope(str, Enum):
    GLOBAL = "global"   # all trees in the tenant
    TREE   = "tree"     # single tree


class SortOrder(str, Enum):
    RELEVANCE   = "relevance"    # ts_rank + trigram composite score
    NAME        = "name"         # alphabetical by surname, given_name
    BIRTH_YEAR  = "birth_year"   # chronological
    UPDATED_AT  = "updated_at"   # recently changed first


# ── Query value objects ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NameSearchQuery:
    """Full-text + fuzzy name search."""
    raw: str                                    # original user input
    tree_id: Optional[uuid.UUID]   = None       # None → global (tenant-scoped)
    tenant_id: Optional[uuid.UUID] = None
    birth_year_min: Optional[int]  = None
    birth_year_max: Optional[int]  = None
    birth_place: Optional[str]     = None
    limit: int                     = 20
    offset: int                    = 0
    sort: SortOrder                = SortOrder.RELEVANCE
    fuzzy: bool                    = True        # enable trigram fallback


@dataclass(frozen=True)
class RelationshipQuery:
    """Find the relationship path between two people."""
    person_id_1: uuid.UUID
    person_id_2: uuid.UUID
    tree_id: uuid.UUID
    tenant_id: uuid.UUID
    max_depth: int = 15              # max hops (BFS stops here)


@dataclass(frozen=True)
class AncestorQuery:
    """All ancestors of a person up to *max_depth* generations."""
    person_id: uuid.UUID
    tree_id: uuid.UUID
    tenant_id: uuid.UUID
    max_depth: int          = 10     # 10 = great-great-great-great-great-grandparents
    include_spouses: bool   = False  # also include spouses of ancestors


@dataclass(frozen=True)
class BranchQuery:
    """All descendants of a person (family branch)."""
    root_person_id: uuid.UUID
    tree_id: uuid.UUID
    tenant_id: uuid.UUID
    max_depth: int = 10
    include_spouses: bool = False


@dataclass(frozen=True)
class RelativeQuery:
    """All relatives within *max_hops* of a person (bidirectional BFS)."""
    person_id: uuid.UUID
    tree_id: uuid.UUID
    tenant_id: uuid.UUID
    max_hops: int = 4    # 4 hops covers 2nd cousins


# ── Result value objects ───────────────────────────────────────────────────────

@dataclass
class PersonSearchHit:
    """A single person result from a name search."""
    person_id: uuid.UUID
    tree_id: uuid.UUID
    given_name: Optional[str]
    surname: Optional[str]
    maiden_name: Optional[str]
    birth_year: Optional[int]
    death_year: Optional[int]
    birth_place: Optional[str]
    is_living: bool
    score: float                = 0.0   # composite relevance score
    matched_fields: list[str]   = field(default_factory=list)


@dataclass
class AncestorHit:
    """A single person in an ancestor/branch result."""
    person_id: uuid.UUID
    given_name: Optional[str]
    surname: Optional[str]
    birth_year: Optional[int]
    death_year: Optional[int]
    depth: int              # generation distance from the query person
    relationship_label: str # "Parent", "Grandparent", "Great-grandparent", etc.
    is_living: bool


@dataclass
class RelationshipPath:
    """
    The shortest path between two people in the tree.
    Each step is a (person_id, role_label) tuple describing how you move
    from one person to the next.
    """
    person_id_1: uuid.UUID
    person_id_2: uuid.UUID
    found: bool
    distance: int                           # number of hops (0 if same person)
    path: list[dict[str, Any]]              # [{person_id, name}, ...]
    relationship_label: Optional[str]       # human-readable: "2nd cousin once removed"
    alternative_label: Optional[str] = None # e.g. "Sister-in-law" for female 1st cousin
    edge_labels: list[str] = field(default_factory=list)  # "parent"|"child"|"spouse"|"sibling" per step


@dataclass
class SearchResults:
    """Wrapper returned by SearchService for all search types."""
    query_type: SearchCategory
    total: int
    hits: list[PersonSearchHit] = field(default_factory=list)
    ancestors: list[AncestorHit] = field(default_factory=list)
    relationship: Optional[RelationshipPath] = None
    took_ms: int = 0


# ── Depth → relationship label ─────────────────────────────────────────────────

def ancestor_label(depth: int) -> str:
    """Return a human-readable label for an ancestor at *depth* generations."""
    labels = {
        1: "Parent",
        2: "Grandparent",
        3: "Great-grandparent",
        4: "2×Great-grandparent",
        5: "3×Great-grandparent",
    }
    if depth in labels:
        return labels[depth]
    return f"{depth - 2}×Great-grandparent"


def descendant_label(depth: int) -> str:
    labels = {
        1: "Child",
        2: "Grandchild",
        3: "Great-grandchild",
        4: "2×Great-grandchild",
        5: "3×Great-grandchild",
    }
    if depth in labels:
        return labels[depth]
    return f"{depth - 1}×Great-grandchild"

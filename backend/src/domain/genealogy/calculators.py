"""Relationship calculators — all pure functions on FamilyGraph.

Algorithms
──────────
ancestors()          BFS upward; returns by generation
descendants()        BFS downward; returns by generation
grandparents()       ancestors at generation 2
great_grandparents() ancestors at generation 3
cousins()            LCA-based; returns KinshipResult with degree/removed
kinship()            full relationship classifier between any two persons
lineage_paths()      DFS; all undirected paths up to a depth limit
lowest_common_ancestors()  shared ancestors closest to both persons

Cousin arithmetic
─────────────────
Given LCA at depth d1 from person1 and d2 from person2:

  degree  = min(d1, d2) - 1
  removed = abs(d1 - d2)

  d1=1, d2=1 → siblings (special-cased before cousin logic)
  d1=2, d2=2 → 1st cousin  (degree=1, removed=0)
  d1=3, d2=3 → 2nd cousin  (degree=2, removed=0)
  d1=2, d2=3 → 1st cousin once removed  (degree=1, removed=1)
  d1=1, d2=2 → aunt/uncle or niece/nephew (degree=0, removed=1 — also special-cased)
"""

from __future__ import annotations

import uuid
from collections import deque
from typing import Optional

from src.domain.genealogy.entities import (
    KinshipResult,
    LineagePath,
    ParentageType,
    RelationshipKind,
)
from src.domain.genealogy.graph import FamilyGraph


# ── Ancestors / descendants ───────────────────────────────────────

def ancestors(
    graph: FamilyGraph,
    person_id: uuid.UUID,
    max_depth: int = 100,
) -> dict[int, list[uuid.UUID]]:
    """
    Return all ancestors organised by generation.
    Generation 1 = parents, 2 = grandparents, 3 = great-grandparents, …
    """
    return graph.ancestors_bfs(person_id, max_depth=max_depth)


def descendants(
    graph: FamilyGraph,
    person_id: uuid.UUID,
    max_depth: int = 100,
) -> dict[int, list[uuid.UUID]]:
    """
    Return all descendants organised by generation.
    Generation 1 = children, 2 = grandchildren, …
    """
    return graph.descendants_bfs(person_id, max_depth=max_depth)


def grandparents(graph: FamilyGraph, person_id: uuid.UUID) -> list[uuid.UUID]:
    """Parents of parents (generation 2)."""
    return ancestors(graph, person_id, max_depth=2).get(2, [])


def great_grandparents(graph: FamilyGraph, person_id: uuid.UUID) -> list[uuid.UUID]:
    """Generation 3 ancestors."""
    return ancestors(graph, person_id, max_depth=3).get(3, [])


def grandchildren(graph: FamilyGraph, person_id: uuid.UUID) -> list[uuid.UUID]:
    return descendants(graph, person_id, max_depth=2).get(2, [])


def great_grandchildren(graph: FamilyGraph, person_id: uuid.UUID) -> list[uuid.UUID]:
    return descendants(graph, person_id, max_depth=3).get(3, [])


# ── Lowest Common Ancestors ───────────────────────────────────────

def lowest_common_ancestors(
    graph: FamilyGraph,
    person1_id: uuid.UUID,
    person2_id: uuid.UUID,
    max_depth: int = 100,
) -> list[tuple[uuid.UUID, int, int]]:
    """
    Find all common ancestors of person1 and person2 together with their
    generation distances.

    Returns a list of (ancestor_id, dist_from_person1, dist_from_person2)
    sorted by (dist1 + dist2) ascending — the "lowest" (closest) first.

    Note: a person is NOT considered their own ancestor here. If person1
    IS person2's ancestor (or vice-versa) the caller should handle that
    before calling this function.
    """
    anc1 = graph.ancestors_flat(person1_id, max_depth=max_depth)
    anc2 = graph.ancestors_flat(person2_id, max_depth=max_depth)

    common_ids = set(anc1.keys()) & set(anc2.keys())

    results = [
        (aid, anc1[aid], anc2[aid])
        for aid in common_ids
    ]
    # Sort: closest combined distance first
    results.sort(key=lambda t: t[1] + t[2])
    return results


# ── Cousin / kinship calculation ──────────────────────────────────

def classify_kinship(
    graph: FamilyGraph,
    person1_id: uuid.UUID,
    person2_id: uuid.UUID,
) -> KinshipResult:
    """
    Determine the relationship between any two persons in the graph.

    Decision tree:
      1. Same person → SELF
      2. Direct parent/child
      3. Grandparent/grandchild
      4. Great-grandparent/great-grandchild
      5. Deeper direct ancestor/descendant
      6. Sibling (full or half)
      7. Aunt/uncle or niece/nephew (LCA at depth 1/2 from one, 2/1 from other)
      8. Cousin (LCA-based)
      9. Spouse (co-parent in a family group)
     10. No connection found → UNKNOWN
    """
    base = KinshipResult(
        person1_id=person1_id,
        person2_id=person2_id,
        kind=RelationshipKind.UNKNOWN,
    )

    # 1. Self
    if person1_id == person2_id:
        base.kind = RelationshipKind.SELF
        return base

    # 2-5. Direct line: is person2 an ancestor of person1?
    anc1_flat = graph.ancestors_flat(person1_id)
    if person2_id in anc1_flat:
        dist = anc1_flat[person2_id]
        kind = _direct_ancestor_kind(dist)
        path = _ancestor_path(graph, person1_id, person2_id)
        return KinshipResult(person1_id=person1_id, person2_id=person2_id,
                             kind=kind, path=path)

    # 2-5. Is person2 a descendant of person1?
    desc1_flat = graph.descendants_flat(person1_id)
    if person2_id in desc1_flat:
        dist = desc1_flat[person2_id]
        kind = _direct_descendant_kind(dist)
        path = graph.shortest_path(person1_id, person2_id) or []
        return KinshipResult(person1_id=person1_id, person2_id=person2_id,
                             kind=kind, path=path)

    # 6. Sibling / half-sibling
    my_fg = graph.family_group_as_child(person1_id)
    their_fg = graph.family_group_as_child(person2_id)

    if my_fg is not None and their_fg is not None:
        if my_fg.id == their_fg.id:
            path = graph.shortest_path(person1_id, person2_id) or []
            return KinshipResult(person1_id=person1_id, person2_id=person2_id,
                                 kind=RelationshipKind.SIBLING,
                                 common_ancestor_ids=my_fg.parent_ids,
                                 path=path)

        shared_parents = my_fg.shared_parents(their_fg)
        if shared_parents:
            path = graph.shortest_path(person1_id, person2_id) or []
            return KinshipResult(person1_id=person1_id, person2_id=person2_id,
                                 kind=RelationshipKind.HALF_SIBLING,
                                 common_ancestor_ids=shared_parents,
                                 path=path)

    # 9. Spouse (co-parent)
    if person2_id in graph.spouses_of(person1_id):
        path = graph.shortest_path(person1_id, person2_id) or []
        return KinshipResult(person1_id=person1_id, person2_id=person2_id,
                             kind=RelationshipKind.SPOUSE, path=path)

    # 7-8. LCA-based (aunt/uncle, cousin)
    lcas = lowest_common_ancestors(graph, person1_id, person2_id)
    if not lcas:
        return base  # UNKNOWN — unconnected

    # Take the LCA(s) with minimum combined distance
    min_combined = lcas[0][1] + lcas[0][2]
    best_lcas = [t for t in lcas if t[1] + t[2] == min_combined]
    _, d1, d2 = best_lcas[0]

    # d1 = distance from person1 to LCA, d2 = distance from person2 to LCA
    orig_d1, orig_d2 = d1, d2
    # Normalise so d1 ≤ d2 for degree/removed calculation
    if d1 > d2:
        d1, d2 = d2, d1

    common_ids = [t[0] for t in best_lcas]
    path = graph.shortest_path(person1_id, person2_id) or []

    # Aunt/uncle vs niece/nephew: the kind describes what person2 IS to person1.
    # If person1 is closer to LCA (d1 < d2): person2 is person1's niece/nephew.
    # If person1 is farther from LCA (d1 > d2): person2 is person1's aunt/uncle.
    if min(orig_d1, orig_d2) == 1 and max(orig_d1, orig_d2) == 2:
        if orig_d1 < orig_d2:
            kind = RelationshipKind.NIECE_NEPHEW
        else:
            kind = RelationshipKind.AUNT_UNCLE
        return KinshipResult(person1_id=person1_id, person2_id=person2_id,
                             kind=kind, common_ancestor_ids=common_ids, path=path)

    # Cousin
    degree = d1 - 1         # 1st cousin: d1=2 → degree=1
    removed = d2 - d1       # 0 = same generation

    return KinshipResult(
        person1_id=person1_id,
        person2_id=person2_id,
        kind=RelationshipKind.COUSIN,
        cousin_degree=degree,
        cousin_removed=removed,
        common_ancestor_ids=common_ids,
        path=path,
    )


def cousins(
    graph: FamilyGraph,
    person_id: uuid.UUID,
    degree: int = 1,
    removed: int = 0,
    max_depth: int = 50,
) -> list[KinshipResult]:
    """
    Find all persons who are the Nth cousin (M times removed) of person_id.

    Strategy: BFS outward from person_id up to (degree + 1 + removed) generations
    in all directions, then classify each candidate and filter.
    """
    # Upper bound on hops: climb degree+1 gens + descend degree+removed gens
    hop_limit = (degree + 1) * 2 + removed + 2
    candidates = _reachable_persons(graph, person_id, max_hops=min(hop_limit, max_depth))

    results: list[KinshipResult] = []
    for cid in candidates:
        if cid == person_id:
            continue
        k = classify_kinship(graph, person_id, cid)
        if (k.kind == RelationshipKind.COUSIN
                and k.cousin_degree == degree
                and k.cousin_removed == removed):
            results.append(k)
    return results


# ── Lineage paths ─────────────────────────────────────────────────

def lineage_paths(
    graph: FamilyGraph,
    origin: uuid.UUID,
    destination: uuid.UUID,
    max_paths: int = 10,
    max_length: int = 20,
) -> list[LineagePath]:
    """
    DFS to find all simple paths between origin and destination.
    Returns up to max_paths paths, each at most max_length hops,
    ordered by length ascending.
    """
    found: list[list[uuid.UUID]] = []
    stack: list[tuple[list[uuid.UUID], set[uuid.UUID]]] = [
        ([origin], {origin})
    ]

    while stack and len(found) < max_paths:
        path, visited = stack.pop()
        current = path[-1]

        if current == destination:
            found.append(path)
            continue

        if len(path) > max_length:
            continue

        for nbr in graph._neighbors(current):
            if nbr not in visited:
                stack.append((path + [nbr], visited | {nbr}))

    found.sort(key=len)

    result: list[LineagePath] = []
    for path_nodes in found:
        labels = _path_edge_labels(graph, path_nodes)
        result.append(LineagePath(nodes=path_nodes, edge_labels=labels))
    return result


# ── Private helpers ───────────────────────────────────────────────

def _direct_ancestor_kind(distance: int) -> RelationshipKind:
    return {
        1: RelationshipKind.PARENT,
        2: RelationshipKind.GRANDPARENT,
        3: RelationshipKind.GREAT_GRANDPARENT,
    }.get(distance, RelationshipKind.ANCESTOR)


def _direct_descendant_kind(distance: int) -> RelationshipKind:
    return {
        1: RelationshipKind.CHILD,
        2: RelationshipKind.GRANDCHILD,
        3: RelationshipKind.GREAT_GRANDCHILD,
    }.get(distance, RelationshipKind.DESCENDANT)


def _ancestor_path(
    graph: FamilyGraph,
    person_id: uuid.UUID,
    target_ancestor_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Climb from person_id upward until target_ancestor_id is reached."""
    path = [person_id]
    current = person_id
    visited: set[uuid.UUID] = {person_id}
    queue: deque[list[uuid.UUID]] = deque([[person_id]])

    while queue:
        p = queue.popleft()
        current = p[-1]
        for parent_id in graph.parents_of(current):
            if parent_id in visited:
                continue
            new_p = p + [parent_id]
            if parent_id == target_ancestor_id:
                return new_p
            visited.add(parent_id)
            queue.append(new_p)
    return path  # fallback


def _reachable_persons(
    graph: FamilyGraph,
    origin: uuid.UUID,
    max_hops: int,
) -> set[uuid.UUID]:
    """BFS outward (undirected) from origin up to max_hops hops."""
    visited: set[uuid.UUID] = {origin}
    queue: deque[tuple[uuid.UUID, int]] = deque([(origin, 0)])
    while queue:
        current, hops = queue.popleft()
        if hops >= max_hops:
            continue
        for nbr in graph._neighbors(current):
            if nbr not in visited:
                visited.add(nbr)
                queue.append((nbr, hops + 1))
    return visited


def _path_edge_labels(graph: FamilyGraph, path: list[uuid.UUID]) -> list[str]:
    """Generate a human-readable label for each step in a path."""
    labels: list[str] = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        if b in graph.parents_of(a):
            labels.append("parent")
        elif b in graph.children_of(a):
            labels.append("child")
        elif b in graph.spouses_of(a):
            labels.append("spouse")
        else:
            labels.append("relative")
    return labels

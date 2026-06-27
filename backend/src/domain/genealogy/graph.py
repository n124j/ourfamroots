"""FamilyGraph — the core in-memory data structure for the genealogy engine.

Structure
─────────
The graph is a bipartite structure:
  • PersonNode  — vertices representing individuals
  • FamilyGroupNode — hyper-edges representing one partnership unit

Adjacency index (all sets, O(1) lookup):
  _person_nodes         : person_id  → PersonNode
  _family_nodes         : fg_id      → FamilyGroupNode
  _parent_of_fgs        : person_id  → set of fg_ids where person is a PARENT
  _child_in_fg          : person_id  → fg_id | None   (at most one)

This mirrors the GEDCOM FAM model: every person is a child in at most one
family group (INDI.FAMC) and a parent in zero or more (INDI.FAMS).
"""

from __future__ import annotations

import uuid
from collections import deque
from typing import Optional

from src.domain.genealogy.entities import (
    FamilyGroupNode,
    ParentageType,
    PersonNode,
    UnionType,
)


class FamilyGraph:
    """
    Immutable-snapshot graph of a single family tree.

    Built by the infrastructure layer (GraphLoader) at the start of every
    service call. The domain service mutates a *copy* (via add_*/remove_*
    methods that return new FamilyGraph instances) before persisting.

    For performance, mutation methods operate in-place on builder instances;
    the service creates a working copy when validation requires it.
    """

    def __init__(self) -> None:
        self._person_nodes: dict[uuid.UUID, PersonNode] = {}
        self._family_nodes: dict[uuid.UUID, FamilyGroupNode] = {}
        # person → family groups where they are a PARENT
        self._parent_of_fgs: dict[uuid.UUID, set[uuid.UUID]] = {}
        # person → single family group where they are a CHILD (or None)
        self._child_in_fg: dict[uuid.UUID, Optional[uuid.UUID]] = {}

    # ── Builder helpers ───────────────────────────────────────────

    def add_person(self, node: PersonNode) -> None:
        self._person_nodes[node.id] = node
        self._parent_of_fgs.setdefault(node.id, set())
        self._child_in_fg.setdefault(node.id, None)

    def add_family_group(self, fg: FamilyGroupNode) -> None:
        self._family_nodes[fg.id] = fg
        for pid in fg.parent_ids:
            self._parent_of_fgs.setdefault(pid, set()).add(fg.id)
        for cid in fg.child_ids:
            self._child_in_fg[cid] = fg.id

    # ── Query — persons ───────────────────────────────────────────

    def get_person(self, person_id: uuid.UUID) -> Optional[PersonNode]:
        return self._person_nodes.get(person_id)

    def has_person(self, person_id: uuid.UUID) -> bool:
        return person_id in self._person_nodes

    def all_person_ids(self) -> set[uuid.UUID]:
        return set(self._person_nodes.keys())

    # ── Query — family groups ─────────────────────────────────────

    def get_family_group(self, fg_id: uuid.UUID) -> Optional[FamilyGroupNode]:
        return self._family_nodes.get(fg_id)

    def family_groups_as_parent(self, person_id: uuid.UUID) -> list[FamilyGroupNode]:
        """Family groups where this person appears as a parent (their marriages/partnerships)."""
        return [
            self._family_nodes[fid]
            for fid in self._parent_of_fgs.get(person_id, set())
            if fid in self._family_nodes
        ]

    def family_group_as_child(self, person_id: uuid.UUID) -> Optional[FamilyGroupNode]:
        """The family group where this person is a child (their family of origin)."""
        fg_id = self._child_in_fg.get(person_id)
        if fg_id is None:
            return None
        return self._family_nodes.get(fg_id)

    # ── Query — relatives ─────────────────────────────────────────

    def parents_of(self, person_id: uuid.UUID) -> list[uuid.UUID]:
        """Direct parents (all parentage types) from the origin family group."""
        fg = self.family_group_as_child(person_id)
        return fg.parent_ids if fg else []

    def children_of(self, person_id: uuid.UUID) -> list[uuid.UUID]:
        """All children across all family groups where this person is a parent."""
        result: list[uuid.UUID] = []
        for fg in self.family_groups_as_parent(person_id):
            result.extend(fg.child_ids)
        return result

    def spouses_of(self, person_id: uuid.UUID) -> list[uuid.UUID]:
        """All co-parents across all family groups."""
        spouses: list[uuid.UUID] = []
        for fg in self.family_groups_as_parent(person_id):
            for pid in fg.parent_ids:
                if pid != person_id and pid not in spouses:
                    spouses.append(pid)
        return spouses

    def siblings_of(self, person_id: uuid.UUID) -> list[uuid.UUID]:
        """All persons sharing the same origin family group (full siblings only here)."""
        fg = self.family_group_as_child(person_id)
        if fg is None:
            return []
        return [cid for cid in fg.child_ids if cid != person_id]

    def half_siblings_of(self, person_id: uuid.UUID) -> dict[uuid.UUID, list[uuid.UUID]]:
        """
        Half-siblings: persons who share exactly ONE parent with person_id
        but come from a different family group.

        Returns {half_sibling_id: [shared_parent_ids]}
        """
        my_parents = set(self.parents_of(person_id))
        if not my_parents:
            return {}

        result: dict[uuid.UUID, list[uuid.UUID]] = {}
        for parent_id in my_parents:
            for fg in self.family_groups_as_parent(parent_id):
                for cid in fg.child_ids:
                    if cid == person_id:
                        continue
                    # cid is in a different fg where person_id is NOT also a child
                    child_fg = self.family_group_as_child(cid)
                    my_fg = self.family_group_as_child(person_id)
                    if child_fg and my_fg and child_fg.id != my_fg.id:
                        result.setdefault(cid, [])
                        if parent_id not in result[cid]:
                            result[cid].append(parent_id)
        return result

    # ── BFS traversal — ancestors ─────────────────────────────────

    def ancestors_bfs(
        self,
        person_id: uuid.UUID,
        max_depth: int = 100,
        parentage_filter: set[ParentageType] | None = None,
    ) -> dict[int, list[uuid.UUID]]:
        """
        Breadth-first ancestor traversal.

        Returns {generation: [person_ids]} where generation 1 = parents,
        2 = grandparents, 3 = great-grandparents, …

        parentage_filter: if set, only follow edges with the given parentage types.
        """
        result: dict[int, list[uuid.UUID]] = {}
        visited: set[uuid.UUID] = {person_id}
        queue: deque[tuple[uuid.UUID, int]] = deque([(person_id, 0)])

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            fg = self.family_group_as_child(current_id)
            if fg is None:
                continue

            for parent_id in fg.parent_ids:
                if parent_id in visited:
                    continue
                # Apply parentage filter if requested
                if parentage_filter is not None:
                    pt = fg.children.get(current_id, ParentageType.UNKNOWN)
                    # parentage_filter applies to the child→fg edge, not parent→fg
                    # We keep the parent if the child's parentage type is in filter
                    if pt not in parentage_filter:
                        continue

                visited.add(parent_id)
                gen = depth + 1
                result.setdefault(gen, []).append(parent_id)
                queue.append((parent_id, gen))

        return result

    def ancestors_flat(
        self,
        person_id: uuid.UUID,
        max_depth: int = 100,
    ) -> dict[uuid.UUID, int]:
        """
        Returns {ancestor_id: minimum_generation_distance} for all ancestors.
        Useful for LCA computation.
        """
        by_gen = self.ancestors_bfs(person_id, max_depth=max_depth)
        flat: dict[uuid.UUID, int] = {}
        for gen, ids in by_gen.items():
            for aid in ids:
                if aid not in flat:
                    flat[aid] = gen
        return flat

    # ── BFS traversal — descendants ───────────────────────────────

    def descendants_bfs(
        self,
        person_id: uuid.UUID,
        max_depth: int = 100,
    ) -> dict[int, list[uuid.UUID]]:
        """
        Breadth-first descendant traversal.

        Returns {generation: [person_ids]} where generation 1 = children,
        2 = grandchildren, …
        """
        result: dict[int, list[uuid.UUID]] = {}
        visited: set[uuid.UUID] = {person_id}
        queue: deque[tuple[uuid.UUID, int]] = deque([(person_id, 0)])

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for child_id in self.children_of(current_id):
                if child_id in visited:
                    continue
                visited.add(child_id)
                gen = depth + 1
                result.setdefault(gen, []).append(child_id)
                queue.append((child_id, gen))

        return result

    def descendants_flat(
        self,
        person_id: uuid.UUID,
        max_depth: int = 100,
    ) -> dict[uuid.UUID, int]:
        """Returns {descendant_id: minimum_generation_distance}."""
        by_gen = self.descendants_bfs(person_id, max_depth=max_depth)
        flat: dict[uuid.UUID, int] = {}
        for gen, ids in by_gen.items():
            for did in ids:
                if did not in flat:
                    flat[did] = gen
        return flat

    def all_descendants(self, person_id: uuid.UUID, max_depth: int = 100) -> set[uuid.UUID]:
        return set(self.descendants_flat(person_id, max_depth).keys())

    def all_ancestors(self, person_id: uuid.UUID, max_depth: int = 100) -> set[uuid.UUID]:
        return set(self.ancestors_flat(person_id, max_depth).keys())

    # ── Shortest undirected path ──────────────────────────────────

    def shortest_path(
        self,
        source: uuid.UUID,
        target: uuid.UUID,
        max_depth: int = 50,
    ) -> list[uuid.UUID] | None:
        """
        BFS on the undirected person graph (edges = parent↔child relationships).
        Returns the ordered list of person IDs [source … target], or None if
        no path exists within max_depth hops.
        """
        if source == target:
            return [source]

        visited: set[uuid.UUID] = {source}
        queue: deque[list[uuid.UUID]] = deque([[source]])

        while queue:
            path = queue.popleft()
            current = path[-1]
            if len(path) > max_depth:
                continue

            neighbors = self._neighbors(current)
            for nbr in neighbors:
                if nbr in visited:
                    continue
                new_path = path + [nbr]
                if nbr == target:
                    return new_path
                visited.add(nbr)
                queue.append(new_path)

        return None

    def _neighbors(self, person_id: uuid.UUID) -> list[uuid.UUID]:
        """Undirected neighbors: parents + children + spouses."""
        seen: set[uuid.UUID] = set()
        result: list[uuid.UUID] = []

        for nid in self.parents_of(person_id) + self.children_of(person_id) + self.spouses_of(person_id):
            if nid not in seen:
                seen.add(nid)
                result.append(nid)
        return result

    # ── Diagnostics ───────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._person_nodes)

    def __repr__(self) -> str:
        return (
            f"<FamilyGraph persons={len(self._person_nodes)} "
            f"family_groups={len(self._family_nodes)}>"
        )

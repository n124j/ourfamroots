"""
Search repository — raw SQL queries for all four search modes.

All queries are tenant/tree scoped and guard against injection via
parameterised queries (no string interpolation of user input).
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.search.entities import (
    AncestorHit,
    AncestorQuery,
    BranchQuery,
    NameSearchQuery,
    PersonSearchHit,
    RelationshipPath,
    RelationshipQuery,
    RelativeQuery,
    SearchCategory,
    SearchResults,
    SortOrder,
    ancestor_label,
    descendant_label,
)

# ── Redis cache import (optional) ─────────────────────────────────────────────
try:
    import redis.asyncio as aioredis  # type: ignore
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

_CACHE_TTL = {
    "name":     120,    # 2 min
    "ancestor": 600,    # 10 min
    "branch":   600,
    "relative": 300,
}


class SearchRepository:
    def __init__(
        self,
        session: AsyncSession,
        redis: Optional[object] = None,   # aioredis.Redis instance
    ) -> None:
        self._session = session
        self._redis   = redis

    # ── Cache helpers ──────────────────────────────────────────────────────────

    def _cache_key(self, prefix: str, *parts: str) -> str:
        digest = hashlib.sha256(":".join(parts).encode()).hexdigest()[:16]
        return f"search:{prefix}:{digest}"

    async def _cache_get(self, key: str) -> Optional[str]:
        if self._redis and _REDIS_AVAILABLE:
            try:
                return await self._redis.get(key)
            except Exception:
                pass
        return None

    async def _cache_set(self, key: str, value: str, ttl: int) -> None:
        if self._redis and _REDIS_AVAILABLE:
            try:
                await self._redis.setex(key, ttl, value)
            except Exception:
                pass

    # ── 1. Name search ─────────────────────────────────────────────────────────

    async def name_search(self, q: NameSearchQuery) -> SearchResults:
        t0 = time.monotonic()

        # Cache check
        cache_key = self._cache_key(
            "name",
            str(q.tree_id or "global"),
            str(q.tenant_id),
            q.raw,
            str(q.birth_year_min),
            str(q.birth_year_max),
        )
        cached = await self._cache_get(cache_key)
        if cached:
            data = json.loads(cached)
            return SearchResults(
                query_type=SearchCategory.NAME,
                total=data["total"],
                hits=[PersonSearchHit(**h) for h in data["hits"]],
                took_ms=int((time.monotonic() - t0) * 1000),
            )

        raw = q.raw.strip()
        hits = await self._fts_query(q, raw)

        # Trigram fallback when FTS returns nothing
        if not hits and q.fuzzy and len(raw) >= 3:
            hits = await self._trigram_query(q, raw)

        await self._cache_set(
            cache_key,
            json.dumps({"total": len(hits), "hits": [_hit_to_dict(h) for h in hits]}),
            _CACHE_TTL["name"],
        )

        return SearchResults(
            query_type=SearchCategory.NAME,
            total=len(hits),
            hits=hits,
            took_ms=int((time.monotonic() - t0) * 1000),
        )

    async def _fts_query(
        self, q: NameSearchQuery, raw: str
    ) -> list[PersonSearchHit]:
        words = raw.split()
        last_word_prefix = words[-1] + ":*" if words else raw + ":*"

        # Build the tsquery inside a CTE so the || operator is valid SQL
        if not raw.endswith(" "):
            tsq_cte = "SELECT plainto_tsquery('simple', unaccent(:raw)) || to_tsquery('simple', unaccent(:prefix_raw)) AS v"
        else:
            tsq_cte = "SELECT plainto_tsquery('simple', unaccent(:raw)) AS v"

        tree_filter = "AND p.tree_id = :tree_id" if q.tree_id else ""

        order_clause = {
            SortOrder.RELEVANCE:  "score DESC, p.display_surname, p.display_given_name",
            SortOrder.NAME:       "p.display_surname, p.display_given_name",
            SortOrder.BIRTH_YEAR: "p.display_surname, p.display_given_name",
            SortOrder.UPDATED_AT: "p.updated_at DESC",
        }.get(q.sort, "score DESC")

        sql = text(f"""
            WITH _tsq AS ({tsq_cte})
            SELECT
                p.id,
                p.tree_id,
                p.display_given_name AS given_name,
                p.display_surname    AS surname,
                p.is_living,
                ts_rank_cd(p.search_vector, _tsq.v, 32) AS score
            FROM
                persons p, _tsq
            WHERE
                p.tenant_id = :tenant_id
                AND p.is_deleted = FALSE
                AND p.search_vector @@ _tsq.v
                {tree_filter}
            ORDER BY {order_clause}
            LIMIT :limit OFFSET :offset
        """)

        params: dict = {
            "tenant_id": str(q.tenant_id),
            "raw": raw,
            "prefix_raw": last_word_prefix,
            "limit": q.limit,
            "offset": q.offset,
        }
        if q.tree_id:
            params["tree_id"] = str(q.tree_id)

        rows = (await self._session.execute(sql, params)).fetchall()
        return [_row_to_person_hit(r) for r in rows]

    async def _trigram_query(
        self, q: NameSearchQuery, raw: str
    ) -> list[PersonSearchHit]:
        """Fuzzy fallback using pg_trgm similarity on concatenated name."""
        tree_filter = "AND p.tree_id = :tree_id" if q.tree_id else ""

        sql = text(f"""
            SELECT
                p.id,
                p.tree_id,
                p.display_given_name AS given_name,
                p.display_surname    AS surname,
                p.is_living,
                greatest(
                    similarity(coalesce(p.display_given_name,'') || ' ' || coalesce(p.display_surname,''), :raw),
                    similarity(coalesce(p.display_surname,''), :raw),
                    similarity(coalesce(p.display_given_name,''), :raw)
                ) AS score
            FROM persons p
            WHERE
                p.tenant_id = :tenant_id
                AND p.is_deleted = FALSE
                AND greatest(
                    similarity(coalesce(p.display_given_name,'') || ' ' || coalesce(p.display_surname,''), :raw),
                    similarity(coalesce(p.display_surname,''), :raw),
                    similarity(coalesce(p.display_given_name,''), :raw)
                ) > 0.25
                {tree_filter}
            ORDER BY score DESC
            LIMIT :limit OFFSET :offset
        """)

        params: dict = {
            "tenant_id": str(q.tenant_id),
            "raw": raw,
            "limit": q.limit,
            "offset": q.offset,
        }
        if q.tree_id:
            params["tree_id"] = str(q.tree_id)

        rows = (await self._session.execute(sql, params)).fetchall()
        return [_row_to_person_hit(r) for r in rows]

    # ── 2. Ancestor BFS ────────────────────────────────────────────────────────

    async def ancestor_search(self, q: AncestorQuery) -> SearchResults:
        t0 = time.monotonic()

        cache_key = self._cache_key(
            "ancestor",
            str(q.tree_id),
            str(q.person_id),
            str(q.max_depth),
        )
        cached = await self._cache_get(cache_key)
        if cached:
            data = json.loads(cached)
            return SearchResults(
                query_type=SearchCategory.ANCESTOR,
                total=data["total"],
                ancestors=[AncestorHit(**a) for a in data["ancestors"]],
                took_ms=int((time.monotonic() - t0) * 1000),
            )

        sql = text("""
            WITH RECURSIVE ancestors AS (
                -- Base: direct parents
                SELECT
                    p.id            AS person_id,
                    p.given_name,
                    p.surname,
                    p.birth_year,
                    p.death_year,
                    p.is_living,
                    1               AS depth
                FROM persons p
                JOIN family_group_members fgm_c
                    ON fgm_c.person_id = :person_id
                    AND fgm_c.role = 'CHILD'
                    AND fgm_c.tree_id = :tree_id
                JOIN family_group_members fgm_p
                    ON fgm_p.family_group_id = fgm_c.family_group_id
                    AND fgm_p.role = 'PARENT'
                    AND fgm_p.person_id = p.id
                WHERE p.is_deleted = FALSE

                UNION

                -- Recursive: go up one generation
                SELECT
                    p2.id,
                    p2.given_name,
                    p2.surname,
                    p2.birth_year,
                    p2.death_year,
                    p2.is_living,
                    a.depth + 1
                FROM ancestors a
                JOIN family_group_members fgm_c2
                    ON fgm_c2.person_id = a.person_id
                    AND fgm_c2.role = 'CHILD'
                    AND fgm_c2.tree_id = :tree_id
                JOIN family_group_members fgm_p2
                    ON fgm_p2.family_group_id = fgm_c2.family_group_id
                    AND fgm_p2.role = 'PARENT'
                JOIN persons p2 ON p2.id = fgm_p2.person_id
                WHERE a.depth < :max_depth
                  AND p2.is_deleted = FALSE
            )
            SELECT DISTINCT ON (person_id) *
            FROM ancestors
            ORDER BY person_id, depth
        """)

        rows = (await self._session.execute(sql, {
            "person_id": str(q.person_id),
            "tree_id": str(q.tree_id),
            "max_depth": q.max_depth,
        })).fetchall()

        ancestors = [
            AncestorHit(
                person_id=uuid.UUID(r.person_id),
                given_name=r.given_name,
                surname=r.surname,
                birth_year=r.birth_year,
                death_year=r.death_year,
                depth=r.depth,
                relationship_label=ancestor_label(r.depth),
                is_living=r.is_living,
            )
            for r in rows
        ]

        payload = {"total": len(ancestors), "ancestors": [_ancestor_to_dict(a) for a in ancestors]}
        await self._cache_set(cache_key, json.dumps(payload), _CACHE_TTL["ancestor"])

        return SearchResults(
            query_type=SearchCategory.ANCESTOR,
            total=len(ancestors),
            ancestors=ancestors,
            took_ms=int((time.monotonic() - t0) * 1000),
        )

    # ── 3. Branch (descendants) ────────────────────────────────────────────────

    async def branch_search(self, q: BranchQuery) -> SearchResults:
        t0 = time.monotonic()

        cache_key = self._cache_key(
            "branch",
            str(q.tree_id),
            str(q.root_person_id),
            str(q.max_depth),
        )
        cached = await self._cache_get(cache_key)
        if cached:
            data = json.loads(cached)
            return SearchResults(
                query_type=SearchCategory.BRANCH,
                total=data["total"],
                ancestors=[AncestorHit(**a) for a in data["ancestors"]],
                took_ms=int((time.monotonic() - t0) * 1000),
            )

        sql = text("""
            WITH RECURSIVE branch AS (
                -- Base: root person
                SELECT
                    p.id            AS person_id,
                    p.given_name,
                    p.surname,
                    p.birth_year,
                    p.death_year,
                    p.is_living,
                    0               AS depth
                FROM persons p
                WHERE p.id = :root_id
                  AND p.tree_id = :tree_id
                  AND p.is_deleted = FALSE

                UNION

                -- Recursive: descend one generation
                SELECT
                    p2.id,
                    p2.given_name,
                    p2.surname,
                    p2.birth_year,
                    p2.death_year,
                    p2.is_living,
                    b.depth + 1
                FROM branch b
                JOIN family_group_members fgm_p
                    ON fgm_p.person_id = b.person_id
                    AND fgm_p.role = 'PARENT'
                    AND fgm_p.tree_id = :tree_id
                JOIN family_group_members fgm_c
                    ON fgm_c.family_group_id = fgm_p.family_group_id
                    AND fgm_c.role = 'CHILD'
                JOIN persons p2 ON p2.id = fgm_c.person_id
                WHERE b.depth < :max_depth
                  AND p2.is_deleted = FALSE
            )
            SELECT DISTINCT ON (person_id) *
            FROM branch
            WHERE depth > 0        -- exclude the root itself
            ORDER BY person_id, depth
        """)

        rows = (await self._session.execute(sql, {
            "root_id": str(q.root_person_id),
            "tree_id": str(q.tree_id),
            "max_depth": q.max_depth,
        })).fetchall()

        descendants = [
            AncestorHit(
                person_id=uuid.UUID(r.person_id),
                given_name=r.given_name,
                surname=r.surname,
                birth_year=r.birth_year,
                death_year=r.death_year,
                depth=r.depth,
                relationship_label=descendant_label(r.depth),
                is_living=r.is_living,
            )
            for r in rows
        ]

        payload = {"total": len(descendants), "ancestors": [_ancestor_to_dict(a) for a in descendants]}
        await self._cache_set(cache_key, json.dumps(payload), _CACHE_TTL["branch"])

        return SearchResults(
            query_type=SearchCategory.BRANCH,
            total=len(descendants),
            ancestors=descendants,
            took_ms=int((time.monotonic() - t0) * 1000),
        )

    # ── 4. Relationship path (BFS) ─────────────────────────────────────────────

    async def relationship_search(self, q: RelationshipQuery) -> SearchResults:
        """
        Find the shortest path between two people using bidirectional BFS.
        Implemented in Python over the adjacency data fetched from Postgres
        (cheaper than a PL/pgSQL BFS for short paths; Postgres CTE for long).
        """
        t0 = time.monotonic()

        if str(q.person_id_1) == str(q.person_id_2):
            return SearchResults(
                query_type=SearchCategory.RELATIONSHIP,
                total=0,
                relationship=RelationshipPath(
                    person_id_1=q.person_id_1,
                    person_id_2=q.person_id_2,
                    found=True,
                    distance=0,
                    path=[],
                    relationship_label="Same person",
                ),
                took_ms=0,
            )

        path = await self._bfs_relationship(q)

        return SearchResults(
            query_type=SearchCategory.RELATIONSHIP,
            total=1 if path.found else 0,
            relationship=path,
            took_ms=int((time.monotonic() - t0) * 1000),
        )

    async def _bfs_relationship(self, q: RelationshipQuery) -> RelationshipPath:
        """
        Python-level BFS using the adjacency list loaded from the DB.
        Loads all person↔family_group edges for the tree once, then does BFS.
        For very large trees the CTE approach would be preferable; this is
        efficient for typical pedigrees (< 10k nodes).
        """
        # Load full adjacency list for the tree
        adj_sql = text("""
            SELECT person_id, family_group_id, role
            FROM family_group_members
            WHERE tree_id = :tree_id
        """)
        rows = (await self._session.execute(adj_sql, {"tree_id": str(q.tree_id)})).fetchall()

        # Build: person → [(family_group_id, role)]
        # And:   family_group → [person_id]  (for navigation)
        from collections import defaultdict
        person_to_fgs: dict[str, list[tuple[str, str]]] = defaultdict(list)
        fg_to_persons: dict[str, list[str]] = defaultdict(list)

        for r in rows:
            person_to_fgs[str(r.person_id)].append((str(r.family_group_id), r.role))
            fg_to_persons[str(r.family_group_id)].append(str(r.person_id))

        # BFS from p1 toward p2
        start = str(q.person_id_1)
        end   = str(q.person_id_2)

        visited: dict[str, Optional[str]] = {start: None}  # node → predecessor
        queue: list[str] = [start]
        found = False

        for _ in range(q.max_depth * 2):  # each hop = 2 BFS levels (person→fg→person)
            if not queue:
                break
            next_queue: list[str] = []
            for pid in queue:
                for fg_id, _role in person_to_fgs.get(pid, []):
                    for neighbor in fg_to_persons.get(fg_id, []):
                        if neighbor not in visited:
                            visited[neighbor] = pid
                            if neighbor == end:
                                found = True
                                break
                            next_queue.append(neighbor)
                    if found:
                        break
                if found:
                    break
            if found:
                break
            queue = next_queue

        if not found:
            return RelationshipPath(
                person_id_1=q.person_id_1,
                person_id_2=q.person_id_2,
                found=False,
                distance=0,
                path=[],
                relationship_label=None,
            )

        # Reconstruct path
        path_ids: list[str] = []
        cur: Optional[str] = end
        while cur is not None:
            path_ids.append(cur)
            cur = visited.get(cur)
        path_ids.reverse()
        distance = len(path_ids) - 1

        # Fetch names for path nodes
        # Build an IN-list directly (path_ids are internal BFS UUIDs, not user input)
        if path_ids:
            uuid_list = ", ".join(f"'{pid}'::uuid" for pid in path_ids)
            name_sql = text(f"""
                SELECT id, display_given_name AS given_name, display_surname AS surname,
                       sex, birth_year
                FROM persons
                WHERE id IN ({uuid_list})
            """)
            name_rows = (await self._session.execute(name_sql)).fetchall()
        else:
            name_rows = []
        name_map = {str(r.id): f"{r.given_name or ''} {r.surname or ''}".strip() for r in name_rows}
        sex_map  = {str(r.id): r.sex for r in name_rows}
        birth_year_map = {str(r.id): r.birth_year for r in name_rows}

        path_steps = [
            {"person_id": pid, "name": name_map.get(pid, pid), "sex": sex_map.get(pid)}
            for pid in path_ids
        ]

        edge_labels = _compute_edge_labels(path_ids, person_to_fgs)
        relationship_label = _infer_specific_label(path_ids, person_to_fgs, sex_map, birth_year_map)

        # For a 1st cousin, also surface the culturally-common in-law alias
        # (female 1st cousin → Sister-in-law, male → Brother-in-law)
        alternative_label: str | None = None
        if relationship_label == "1st Cousins":
            target_sex = sex_map.get(end)
            if target_sex == "FEMALE":
                alternative_label = "Sister-in-law"
            elif target_sex == "MALE":
                alternative_label = "Brother-in-law"

        return RelationshipPath(
            person_id_1=q.person_id_1,
            person_id_2=q.person_id_2,
            found=True,
            distance=distance,
            path=path_steps,
            relationship_label=relationship_label,
            alternative_label=alternative_label,
            edge_labels=edge_labels,
        )

    # ── 5. All relatives (bidirectional BFS) ──────────────────────────────────

    async def relative_search(self, q: RelativeQuery) -> SearchResults:
        t0 = time.monotonic()

        cache_key = self._cache_key(
            "relative",
            str(q.tree_id),
            str(q.person_id),
            str(q.max_hops),
        )
        cached = await self._cache_get(cache_key)
        if cached:
            data = json.loads(cached)
            return SearchResults(
                query_type=SearchCategory.RELATIVE,
                total=data["total"],
                ancestors=[AncestorHit(**a) for a in data["ancestors"]],
                took_ms=int((time.monotonic() - t0) * 1000),
            )

        # Uses a Postgres CTE that walks both up AND down from the person
        sql = text("""
            WITH RECURSIVE relatives AS (
                SELECT
                    p.id            AS person_id,
                    p.given_name,
                    p.surname,
                    p.birth_year,
                    p.death_year,
                    p.is_living,
                    0               AS hops
                FROM persons p
                WHERE p.id = :person_id
                  AND p.tree_id = :tree_id
                  AND p.is_deleted = FALSE

                UNION

                SELECT
                    p2.id,
                    p2.given_name,
                    p2.surname,
                    p2.birth_year,
                    p2.death_year,
                    p2.is_living,
                    r.hops + 1
                FROM relatives r
                JOIN family_group_members fgm1
                    ON fgm1.person_id = r.person_id
                    AND fgm1.tree_id = :tree_id
                JOIN family_group_members fgm2
                    ON fgm2.family_group_id = fgm1.family_group_id
                    AND fgm2.person_id != r.person_id
                JOIN persons p2 ON p2.id = fgm2.person_id
                WHERE r.hops < :max_hops
                  AND p2.is_deleted = FALSE
            )
            SELECT DISTINCT ON (person_id) *
            FROM relatives
            WHERE person_id != :person_id
            ORDER BY person_id, hops
        """)

        rows = (await self._session.execute(sql, {
            "person_id": str(q.person_id),
            "tree_id": str(q.tree_id),
            "max_hops": q.max_hops,
        })).fetchall()

        relatives = [
            AncestorHit(
                person_id=uuid.UUID(r.person_id),
                given_name=r.given_name,
                surname=r.surname,
                birth_year=r.birth_year,
                death_year=r.death_year,
                depth=r.hops,
                relationship_label=f"{r.hops} hop{'s' if r.hops != 1 else ''} away",
                is_living=r.is_living,
            )
            for r in rows
        ]

        payload = {"total": len(relatives), "ancestors": [_ancestor_to_dict(a) for a in relatives]}
        await self._cache_set(cache_key, json.dumps(payload), _CACHE_TTL["relative"])

        return SearchResults(
            query_type=SearchCategory.RELATIVE,
            total=len(relatives),
            ancestors=relatives,
            took_ms=int((time.monotonic() - t0) * 1000),
        )


# ── Serialisation helpers ──────────────────────────────────────────────────────

def _row_to_person_hit(r) -> PersonSearchHit:
    return PersonSearchHit(
        person_id=uuid.UUID(str(r.id)),
        tree_id=uuid.UUID(str(r.tree_id)),
        given_name=r.given_name or None,
        surname=r.surname or None,
        maiden_name=None,
        birth_year=None,
        death_year=None,
        birth_place=None,
        is_living=r.is_living,
        score=float(r.score or 0),
    )


def _hit_to_dict(h: PersonSearchHit) -> dict:
    return {
        "person_id": str(h.person_id),
        "tree_id": str(h.tree_id),
        "given_name": h.given_name,
        "surname": h.surname,
        "maiden_name": h.maiden_name,
        "birth_year": h.birth_year,
        "death_year": h.death_year,
        "birth_place": h.birth_place,
        "is_living": h.is_living,
        "score": h.score,
        "matched_fields": h.matched_fields,
    }


def _ancestor_to_dict(a: AncestorHit) -> dict:
    return {
        "person_id": str(a.person_id),
        "given_name": a.given_name,
        "surname": a.surname,
        "birth_year": a.birth_year,
        "death_year": a.death_year,
        "depth": a.depth,
        "relationship_label": a.relationship_label,
        "is_living": a.is_living,
    }


def _degree_to_label(distance: int) -> str:
    """Generic fallback label when roles cannot be determined."""
    labels = {
        0: "Same person",
        1: "Parent, child, sibling, or spouse",
        2: "Grandparent/grandchild or uncle/aunt/nephew/niece",
        3: "Great-grandparent/grandchild or 1st cousin",
        4: "1st cousin once removed or 2×great-grandparent/grandchild",
        5: "2nd cousin or 2×great-grandparent once removed",
        6: "2nd cousin once removed",
    }
    return labels.get(distance, f"Distant relative ({distance} steps)")


def _compute_edge_labels(
    path_ids: list[str],
    person_to_fgs: dict[str, list[tuple[str, str]]],
) -> list[str]:
    """Return a label for each consecutive pair in path_ids.

    Labels: "parent" | "child" | "spouse" | "sibling" | "relative"
    From A's perspective going to B:
      - "child"   = B is A's child
      - "parent"  = B is A's parent
      - "spouse"  = B is A's co-parent (partner)
      - "sibling" = both A and B are children of the same family group
    """
    labels: list[str] = []
    for i in range(len(path_ids) - 1):
        a, b = path_ids[i], path_ids[i + 1]
        fgs_a = {fg_id: role for fg_id, role in person_to_fgs.get(a, [])}
        fgs_b = {fg_id: role for fg_id, role in person_to_fgs.get(b, [])}
        shared = set(fgs_a.keys()) & set(fgs_b.keys())
        label = "relative"
        for fg_id in shared:
            ra, rb = fgs_a[fg_id].upper(), fgs_b[fg_id].upper()
            if ra == "PARENT" and rb == "CHILD":
                label = "child"
                break
            elif ra == "CHILD" and rb == "PARENT":
                label = "parent"
                break
            elif ra == "PARENT" and rb == "PARENT":
                label = "spouse"
                break
            elif ra == "CHILD" and rb == "CHILD":
                label = "sibling"
                break
        labels.append(label)
    return labels


def _sex_aware_label(
    label_male: str,
    label_female: str,
    label_generic: str,
    person_id: str,
    sex_map: dict[str, str | None],
) -> str:
    sex = (sex_map.get(person_id) or "").upper()
    if sex == "MALE":
        return label_male
    if sex == "FEMALE":
        return label_female
    return label_generic


def _is_elder(
    person_a: str,
    person_b: str,
    birth_year_map: dict[str, int | None],
) -> bool | None:
    """Return True if person_a is elder than person_b, False if younger, None if unknown."""
    ya = birth_year_map.get(person_a)
    yb = birth_year_map.get(person_b)
    if ya is None or yb is None:
        return None
    if ya < yb:
        return True
    if ya > yb:
        return False
    return None


def _infer_specific_label(
    path_ids: list[str],
    person_to_fgs: dict[str, list[tuple[str, str]]],
    sex_map: dict[str, str | None] | None = None,
    birth_year_map: dict[str, int | None] | None = None,
) -> str:
    """
    Derive a precise relationship label by inspecting PARENT/CHILD roles along
    the BFS path.  Falls back to _degree_to_label when the pattern is unknown.

    Each 'hop' in the path goes through exactly one shared family group.
    The role each person holds in that group determines direction (up/down/lateral).
    """
    if sex_map is None:
        sex_map = {}
    if birth_year_map is None:
        birth_year_map = {}

    distance = len(path_ids) - 1
    if distance == 0:
        return "Same person"

    s1 = (sex_map.get(path_ids[0]) or "").upper()
    s2 = (sex_map.get(path_ids[-1]) or "").upper()

    # Helper: find the first shared family group between two people and return
    # (role_of_a, role_of_b).  Returns (None, None) when no shared group exists.
    def roles_in_shared_fg(a: str, b: str) -> tuple[str | None, str | None]:
        a_fgs = {fg: role for fg, role in person_to_fgs.get(a, [])}
        b_fgs = {fg: role for fg, role in person_to_fgs.get(b, [])}
        for fg in a_fgs:
            if fg in b_fgs:
                return a_fgs[fg], b_fgs[fg]
        return None, None

    if distance == 1:
        r1, r2 = roles_in_shared_fg(path_ids[0], path_ids[1])
        if r1 == "CHILD" and r2 == "CHILD":
            if s1 == "MALE" and s2 == "MALE":
                return "Brothers"
            if s1 == "FEMALE" and s2 == "FEMALE":
                return "Sisters"
            if {s1, s2} == {"MALE", "FEMALE"}:
                return "Brother/Sister"
            return "Siblings"
        if r1 == "PARENT" and r2 == "CHILD":
            p = _sex_aware_label("Father", "Mother", "Parent", path_ids[0], sex_map)
            c = _sex_aware_label("Son", "Daughter", "Child", path_ids[1], sex_map)
            return f"{p} / {c}"
        if r1 == "CHILD" and r2 == "PARENT":
            c = _sex_aware_label("Son", "Daughter", "Child", path_ids[0], sex_map)
            p = _sex_aware_label("Father", "Mother", "Parent", path_ids[1], sex_map)
            return f"{c} / {p}"
        if r1 == "PARENT" and r2 == "PARENT":
            return "Husband/Wife"
        return "Direct family member"

    if distance == 2:
        p1, mid, p2 = path_ids
        r1,  r_m1 = roles_in_shared_fg(p1,  mid)
        r_m2, r2  = roles_in_shared_fg(mid, p2)
        combo = (r1, r_m1, r_m2, r2)

        if combo == ("PARENT", "CHILD", "PARENT", "CHILD"):
            gp = _sex_aware_label("Grandfather", "Grandmother", "Grandparent", path_ids[0], sex_map)
            gc = _sex_aware_label("Grandson", "Granddaughter", "Grandchild", path_ids[-1], sex_map)
            return f"{gp} / {gc}"
        if combo == ("CHILD", "PARENT", "CHILD", "PARENT"):
            gc = _sex_aware_label("Grandson", "Granddaughter", "Grandchild", path_ids[0], sex_map)
            gp = _sex_aware_label("Grandfather", "Grandmother", "Grandparent", path_ids[-1], sex_map)
            return f"{gc} / {gp}"
        if combo == ("CHILD", "PARENT", "PARENT", "CHILD"):
            return "Half-siblings / Step-siblings"
        if combo == ("PARENT", "CHILD", "CHILD", "PARENT"):
            return "Co-parents"
        if combo == ("CHILD", "CHILD", "PARENT", "CHILD"):
            ua = _sex_aware_label("Uncle", "Aunt", "Uncle/Aunt", path_ids[0], sex_map)
            nn = _sex_aware_label("Nephew", "Niece", "Nephew/Niece", path_ids[-1], sex_map)
            return f"{ua}/{nn}"
        if combo == ("CHILD", "PARENT", "CHILD", "CHILD"):
            nn = _sex_aware_label("Nephew", "Niece", "Nephew/Niece", path_ids[0], sex_map)
            ua = _sex_aware_label("Uncle", "Aunt", "Uncle/Aunt", path_ids[-1], sex_map)
            return f"{nn}/{ua}"
        if combo == ("PARENT", "CHILD", "CHILD", "CHILD"):
            gp = _sex_aware_label("Grandfather", "Grandmother", "Grandparent", path_ids[0], sex_map)
            gc = _sex_aware_label("Grandson", "Granddaughter", "Grandchild", path_ids[-1], sex_map)
            return f"{gp} / {gc}"
        if combo == ("CHILD", "CHILD", "CHILD", "PARENT"):
            gc = _sex_aware_label("Grandson", "Granddaughter", "Grandchild", path_ids[0], sex_map)
            gp = _sex_aware_label("Grandfather", "Grandmother", "Grandparent", path_ids[-1], sex_map)
            return f"{gc} / {gp}"
        # In-law: sibling's spouse
        # Path: Person1 → Mid(sibling) → Person2(spouse)
        # Compare Mid vs Person1 to determine elder/younger sibling
        if combo == ("CHILD", "CHILD", "PARENT", "PARENT"):
            s_mid = (sex_map.get(path_ids[1]) or "").upper()
            mid_elder = _is_elder(path_ids[1], path_ids[0], birth_year_map)
            if s_mid == "MALE":
                if mid_elder is True:
                    return _sex_aware_label(
                        "Brother-in-law (elder brother's husband)",
                        "Sister-in-law (elder brother's wife)",
                        "Brother-in-law/Sister-in-law", path_ids[-1], sex_map,
                    )
                if mid_elder is False:
                    return _sex_aware_label(
                        "Brother-in-law (younger brother's husband)",
                        "Sister-in-law (younger brother's wife)",
                        "Brother-in-law/Sister-in-law", path_ids[-1], sex_map,
                    )
                return _sex_aware_label(
                    "Brother-in-law (brother's husband)",
                    "Sister-in-law (brother's wife)",
                    "Brother-in-law/Sister-in-law", path_ids[-1], sex_map,
                )
            if s_mid == "FEMALE":
                if mid_elder is True:
                    return _sex_aware_label(
                        "Brother-in-law (elder sister's husband)",
                        "Sister-in-law (elder sister's wife)",
                        "Brother-in-laws", path_ids[-1], sex_map,
                    )
                if mid_elder is False:
                    return _sex_aware_label(
                        "Brother-in-law (younger sister's husband)",
                        "Sister-in-law (younger sister's wife)",
                        "Brother-in-laws", path_ids[-1], sex_map,
                    )
                return "Brother-in-laws"
            return _sex_aware_label("Brother-in-law", "Sister-in-law", "Brother-in-law/Sister-in-law", path_ids[-1], sex_map)
        # In-law: spouse's sibling
        # Path: Person1 → Mid(spouse) → Person2(sibling)
        # Compare Person2 vs Mid(spouse) to determine elder/younger
        if combo == ("PARENT", "PARENT", "CHILD", "CHILD"):
            p2_elder = _is_elder(path_ids[-1], path_ids[1], birth_year_map)
            if s1 == "MALE":
                if s2 == "MALE":
                    if p2_elder is True:
                        return "Elder brother-in-law"
                    if p2_elder is False:
                        return "Younger brother-in-law"
                    return "Brother-in-laws"
                if s2 == "FEMALE":
                    return "Sister-in-laws"
            if s1 == "FEMALE":
                if s2 == "MALE":
                    if p2_elder is True:
                        return "Brother-in-law (husband's elder brother)"
                    if p2_elder is False:
                        return "Brother-in-law (husband's younger brother)"
                    return "Brother-in-laws"
                if s2 == "FEMALE":
                    return "Sister-in-laws"
            return _sex_aware_label("Brother-in-law", "Sister-in-law", "Brother-in-law/Sister-in-law", path_ids[-1], sex_map)
        # In-law: spouse's parent (bidirectional label)
        if combo == ("PARENT", "PARENT", "CHILD", "PARENT"):
            parent = _sex_aware_label("Father-in-law", "Mother-in-law", "Parent-in-law", path_ids[-1], sex_map)
            child_in = _sex_aware_label("Son-in-law", "Daughter-in-law", "Child-in-law", path_ids[0], sex_map)
            return f"{child_in}/{parent}"
        # In-law: child's spouse
        if combo == ("PARENT", "CHILD", "PARENT", "PARENT"):
            return _sex_aware_label("Son-in-law", "Daughter-in-law", "Child-in-law", path_ids[-1], sex_map)

        return _degree_to_label(distance)

    if distance == 3:
        p1, a, b, p2 = path_ids
        r_p1, r_a1 = roles_in_shared_fg(p1, a)
        r_a2, r_b1 = roles_in_shared_fg(a,  b)
        r_b2, r_p2 = roles_in_shared_fg(b,  p2)
        roles6 = (r_p1, r_a1, r_a2, r_b1, r_b2, r_p2)

        if roles6 in (
            ("CHILD",  "PARENT", "CHILD",  "CHILD",  "PARENT", "CHILD"),
            ("PARENT", "CHILD",  "CHILD",  "CHILD",  "CHILD",  "PARENT"),
        ):
            return "1st Cousins"
        if roles6 == ("CHILD", "PARENT", "CHILD", "PARENT", "CHILD", "PARENT"):
            ggc = _sex_aware_label("Great-grandson", "Great-granddaughter", "Great-grandchild", path_ids[0], sex_map)
            ggp = _sex_aware_label("Great-grandfather", "Great-grandmother", "Great-grandparent", path_ids[-1], sex_map)
            return f"{ggc} / {ggp}"
        if roles6 == ("PARENT", "CHILD", "PARENT", "CHILD", "PARENT", "CHILD"):
            ggp = _sex_aware_label("Great-grandfather", "Great-grandmother", "Great-grandparent", path_ids[0], sex_map)
            ggc = _sex_aware_label("Great-grandson", "Great-granddaughter", "Great-grandchild", path_ids[-1], sex_map)
            return f"{ggp} / {ggc}"
        if roles6 == ("CHILD", "PARENT", "CHILD", "PARENT", "CHILD", "CHILD"):
            gn = _sex_aware_label("Great-nephew", "Great-niece", "Great-nephew/niece", path_ids[0], sex_map)
            gu = _sex_aware_label("Great-uncle", "Great-aunt", "Great-uncle/aunt", path_ids[-1], sex_map)
            return f"{gn}/{gu}"
        if roles6 == ("CHILD", "CHILD", "PARENT", "CHILD", "PARENT", "CHILD"):
            gu = _sex_aware_label("Great-uncle", "Great-aunt", "Great-uncle/aunt", path_ids[0], sex_map)
            gn = _sex_aware_label("Great-nephew", "Great-niece", "Great-nephew/niece", path_ids[-1], sex_map)
            return f"{gu}/{gn}"
        # In-law: spouse's sibling's spouse (co-in-law)
        if roles6 == ("PARENT", "PARENT", "CHILD", "CHILD", "PARENT", "PARENT"):
            return _sex_aware_label(
                "Co-brother-in-law", "Co-sister-in-law", "Co-in-law",
                path_ids[-1], sex_map,
            )
        # In-law: sibling's spouse's sibling
        if roles6 == ("CHILD", "CHILD", "PARENT", "PARENT", "CHILD", "CHILD"):
            return _sex_aware_label(
                "Co-brother-in-law", "Co-sister-in-law", "Co-in-law",
                path_ids[-1], sex_map,
            )

        return _degree_to_label(distance)

    return _degree_to_label(distance)

# Search Engine Architecture

## Overview

OurFamRoots search operates on four distinct query types, each requiring different
data access strategies:

| Query type       | Strategy                        | Primary index             |
|------------------|---------------------------------|---------------------------|
| Name search      | PostgreSQL FTS + pg_trgm fuzzy  | GIN on `persons_fts`      |
| Relationship     | Recursive CTE graph traversal   | B-tree on FK columns      |
| Ancestor search  | BFS CTE + depth filter          | B-tree + BRIN on tree_id  |
| Family branch    | Bidirectional BFS CTE           | B-tree on FK columns      |

Elasticsearch is **optional** and is additive — it provides ranked relevance scoring
and phonetic matching (Soundex/Metaphone) for large tenants. The PostgreSQL layer
is always the source of truth; ES is a read replica updated via Celery tasks.

---

## PostgreSQL Full-Text Search

### tsvector strategy

Each person row has a generated `search_vector` column that combines:

```sql
setweight(to_tsvector('simple', coalesce(given_name, '')), 'A')  -- highest weight
|| setweight(to_tsvector('simple', coalesce(surname, '')), 'A')
|| setweight(to_tsvector('simple', coalesce(maiden_name, '')), 'B')
|| setweight(to_tsvector('simple', coalesce(birth_place, '')), 'C')
|| setweight(to_tsvector('simple', coalesce(notes, '')), 'D')
```

`'simple'` dictionary is used (not `'english'`) because names don't benefit from
English stemming — "John" should not become "john" and miss "Johns".

### Fuzzy name matching

`pg_trgm` trigram indexes power prefix and similarity search:

```sql
-- Finds "Johnson" when searching "Johnso" (prefix) or "Jonhson" (typo)
WHERE similarity(given_name || ' ' || surname, $query) > 0.3
ORDER BY similarity(...) DESC
```

### Trigram vs. FTS decision tree

```
Query length ≥ 3 chars AND no wildcards?
  → Try tsvector plainto_tsquery first (fast, ranked)
  → If zero results: fall back to trigram similarity (fuzzy)
Query has wildcard (*)?
  → to_tsquery with prefix operator: 'john:*'
Query length < 3 chars?
  → Prefix LIKE only (trgm not effective below 3-grams)
```

---

## Graph Traversal for Relationships

The genealogy graph is stored as two tables:
- `persons` — nodes
- `family_group_members` — edges (person ↔ family_group, with role PARENT/CHILD)

A **recursive CTE** walks the graph bidirectionally:

```sql
-- Ancestor BFS (climb via PARENT role → family_group → other PARENT = grandparent)
WITH RECURSIVE ancestors AS (
  -- Base: direct parents
  SELECT p.id, p.given_name, p.surname, 1 AS depth
  FROM persons p
  JOIN family_group_members fgm_child ON fgm_child.person_id = $target
    AND fgm_child.role = 'CHILD'
  JOIN family_group_members fgm_parent ON fgm_parent.family_group_id = fgm_child.family_group_id
    AND fgm_parent.role = 'PARENT'
    AND fgm_parent.person_id = p.id
  UNION ALL
  -- Recursive: climb one generation
  SELECT p2.id, p2.given_name, p2.surname, a.depth + 1
  FROM ancestors a
  JOIN family_group_members fgm_child ON fgm_child.person_id = a.id
    AND fgm_child.role = 'CHILD'
  JOIN family_group_members fgm_parent ON fgm_parent.family_group_id = fgm_child.family_group_id
    AND fgm_parent.role = 'PARENT'
  JOIN persons p2 ON p2.id = fgm_parent.person_id
  WHERE a.depth < $max_depth        -- guards against cycles in malformed data
)
SELECT DISTINCT ON (id) * FROM ancestors ORDER BY id, depth;
```

### Cycle protection

Real genealogy data sometimes has data entry errors (a person listed as their own
ancestor). The `WHERE depth < $max_depth` clause caps BFS at 30 generations
(sufficient for any real pedigree).

### Family branch

A branch is all descendants of a root person. Uses the same CTE pattern but
descends instead of ascends:

```sql
WITH RECURSIVE branch AS (
  SELECT id, 0 AS depth FROM persons WHERE id = $root
  UNION ALL
  SELECT p.id, b.depth + 1
  FROM branch b
  JOIN family_group_members fgm_p ON fgm_p.person_id = b.id AND fgm_p.role = 'PARENT'
  JOIN family_group_members fgm_c ON fgm_c.family_group_id = fgm_p.family_group_id
    AND fgm_c.role = 'CHILD'
  JOIN persons p ON p.id = fgm_c.person_id
  WHERE b.depth < 30
)
SELECT DISTINCT ON (id) * FROM branch ORDER BY id, depth;
```

---

## Index Design

```sql
-- Full-text search
CREATE INDEX idx_persons_search_vector ON persons USING GIN (search_vector);

-- Trigram (fuzzy name matching)
CREATE INDEX idx_persons_given_trgm  ON persons USING GIN (given_name  gin_trgm_ops);
CREATE INDEX idx_persons_surname_trgm ON persons USING GIN (surname     gin_trgm_ops);

-- Graph traversal hot paths
CREATE INDEX idx_fgm_person_id  ON family_group_members (person_id,  family_group_id);
CREATE INDEX idx_fgm_fg_role    ON family_group_members (family_group_id, role, person_id);

-- Tenant / tree scoping (all queries are tenant-scoped)
CREATE INDEX idx_persons_tree   ON persons (tree_id, tenant_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_fgm_tree       ON family_group_members (tree_id);

-- Date range filtering (birth year range search)
CREATE INDEX idx_persons_birth_year ON persons (birth_year) WHERE birth_year IS NOT NULL;
```

---

## Result Ranking

Name search results are scored using a composite rank:

```
score = 0.4 * ts_rank(search_vector, query)
      + 0.4 * similarity(full_name, raw_query)
      + 0.2 * recency_boost          -- recently edited persons float up
```

`ts_rank_cd` (cover density) is used for multi-word queries because it rewards
documents where query terms appear close together.

---

## Optional Elasticsearch Integration

When `ELASTICSEARCH_URL` is set:

1. A Celery task `index_person` fires on every person create/update/delete.
2. The ES index stores a denormalised snapshot: names, birth/death places, relationships summary.
3. ES provides phonetic analysis (Metaphone via `analysis-phonetic` plugin) for
   "sounds-like" name matching (e.g. "Smyth" finds "Smith").
4. The `SearchService` checks `USE_ELASTICSEARCH` env flag and routes to ES for
   name queries; graph traversal queries always use PostgreSQL.

ES index mapping:

```json
{
  "mappings": {
    "properties": {
      "id":          { "type": "keyword" },
      "tree_id":     { "type": "keyword" },
      "tenant_id":   { "type": "keyword" },
      "given_name":  { "type": "text", "analyzer": "name_analyzer",
                       "fields": { "phonetic": { "type": "text", "analyzer": "phonetic" } } },
      "surname":     { "type": "text", "analyzer": "name_analyzer",
                       "fields": { "phonetic": { "type": "text", "analyzer": "phonetic" } } },
      "birth_year":  { "type": "integer" },
      "birth_place": { "type": "text" },
      "death_year":  { "type": "integer" }
    }
  }
}
```

---

## Query Performance Targets

| Query               | Expected p99   | Notes                                     |
|---------------------|----------------|-------------------------------------------|
| Name FTS (indexed)  | < 10 ms        | GIN index on tsvector                     |
| Fuzzy name (trgm)   | < 50 ms        | trgm similarity, top-10 only              |
| Ancestor BFS 10gen  | < 20 ms        | Recursive CTE, indexed FKs                |
| Ancestor BFS 30gen  | < 200 ms       | Worst-case full pedigree                  |
| Branch (1k nodes)   | < 100 ms       | Recursive CTE + DISTINCT                  |
| Relationship check  | < 5 ms         | Short-circuit BFS: target found at depth N|

---

## Redis Caching Layer

Expensive graph queries are cached in Redis:

```
search:ancestors:{tree_id}:{person_id}:{max_depth}  TTL 10 min
search:branch:{tree_id}:{person_id}                  TTL 10 min
search:name:{tree_id}:{query_hash}                   TTL 2 min
```

Cache is invalidated on any person or family_group_member write within the tree.

---

## Search Modes

```
GET /search?q=John+Smith&scope=global        ← cross-tree (tenant-scoped)
GET /trees/{id}/search?q=John&category=name  ← within one tree
GET /trees/{id}/persons/{id}/ancestors?max_depth=10
GET /trees/{id}/persons/{id}/descendants?max_depth=5
GET /trees/{id}/persons/{id}/relatives       ← all relatives within N hops
GET /trees/{id}/persons/{id}/relationship?target={id2}  ← path between two people
```

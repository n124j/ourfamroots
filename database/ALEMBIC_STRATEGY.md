# OurFamRoots — Alembic Migration Strategy

## Overview

OurFamRoots uses **Alembic** (SQLAlchemy's migration tool) for managing all schema changes.
The SQL DDL files (`V001__create_enums.sql` → `V015__row_level_security.sql`) represent the
**initial baseline** and are applied once via a seeded Alembic revision.
Ongoing changes are expressed as individual Alembic revisions.

---

## Directory Layout

```
alembic/
├── alembic.ini               # Database URL, script_location, etc.
├── env.py                    # Migration environment (connection setup)
├── script.py.mako            # Revision file template
└── versions/
    ├── 0001_baseline.py      # Seeds V001–V015 DDL (initial schema)
    ├── 0002_....py           # First incremental change
    └── ...
```

---

## Naming Convention

All auto-generated constraint names follow the Alembic naming convention
configured in `env.py` to prevent anonymous constraints:

```python
from sqlalchemy import MetaData

convention = {
    "ix":  "ix_%(column_0_label)s",
    "uq":  "uq_%(table_name)s_%(column_0_name)s",
    "ck":  "ck_%(table_name)s_%(constraint_name)s",
    "fk":  "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk":  "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)
```

---

## Zero-Downtime Patterns

### Adding a nullable column
```sql
-- Safe: no table lock beyond metadata update
ALTER TABLE persons ADD COLUMN middle_name text;
```

### Adding a NOT NULL column (expand-contract)
```sql
-- Step 1: Add nullable (deploy v1)
ALTER TABLE persons ADD COLUMN nationality text;

-- Step 2: Backfill in batches (background job)
UPDATE persons SET nationality = 'UNKNOWN'
WHERE nationality IS NULL AND id > $last_id LIMIT 5000;

-- Step 3: Add NOT NULL + default (deploy v2)
ALTER TABLE persons ALTER COLUMN nationality SET DEFAULT 'UNKNOWN';
ALTER TABLE persons ALTER COLUMN nationality SET NOT NULL;
```

### Adding an index
```sql
-- Always CONCURRENTLY to avoid table lock
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_persons_nationality
    ON persons (tenant_id, nationality);
```

### Renaming a column (expand-contract)
```sql
-- Step 1: Add new column (deploy v1)
ALTER TABLE persons ADD COLUMN birth_year integer;

-- Step 2: Backfill + dual-write in app (deploy v2)
UPDATE persons SET birth_year = EXTRACT(YEAR FROM birth_date)::int
WHERE birth_year IS NULL;

-- Step 3: Drop old column (deploy v3, after all readers updated)
ALTER TABLE persons DROP COLUMN birth_date;
```

### Adding a new partition month
```sql
-- Called by pg_cron on the 25th of each month
CALL create_next_month_partitions(date_trunc('month', now()) + INTERVAL '1 month');
```

---

## Partition Maintenance Schedule

| Task | Schedule | Mechanism |
|------|----------|-----------|
| Create next month's partitions | 25th of each month, 02:00 UTC | pg_cron |
| Archive partitions older than 12 months to S3 | 1st of each month, 03:00 UTC | Celery beat |
| Detach archived partitions from parent table | After S3 confirmation | Celery task |

### pg_cron job (installed once by DBA)
```sql
SELECT cron.schedule(
    'create-monthly-partitions',
    '0 2 25 * *',
    $$CALL create_next_month_partitions(
        date_trunc('month', now()) + INTERVAL '1 month'
    );$$
);
```

---

## Baseline Revision

The initial Alembic revision (`0001_baseline.py`) runs the 15 DDL files in order:

```python
# alembic/versions/0001_baseline.py

"""Initial schema baseline

Revision ID: 0001
Create Date: 2025-01-01
"""

from alembic import op
import os

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

DDL_FILES = [
    'V001__create_enums.sql',
    'V002__create_core_tables.sql',
    'V003__create_tree_tables.sql',
    'V004__create_person_tables.sql',
    'V005__create_family_tables.sql',
    'V006__create_event_tables.sql',
    'V007__create_source_tables.sql',
    'V008__create_media_tables.sql',
    'V009__create_dna_tables.sql',
    'V010__create_collaboration_tables.sql',
    'V011__create_audit_tables.sql',
    'V012__create_job_tables.sql',
    'V013__create_indexes.sql',
    'V014__create_triggers.sql',
    'V015__row_level_security.sql',
]

def upgrade():
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'migrations')
    conn = op.get_bind()
    for fname in DDL_FILES:
        path = os.path.join(base, fname)
        with open(path) as f:
            conn.execute(f.read())

def downgrade():
    # Full teardown — only used in dev/test
    op.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
```

---

## Rollback Policy

| Change type | Rollback approach |
|-------------|-------------------|
| New nullable column | `ALTER TABLE ... DROP COLUMN` |
| New index | `DROP INDEX CONCURRENTLY` |
| New table | `DROP TABLE` |
| NOT NULL added | `ALTER COLUMN ... DROP NOT NULL` |
| Partition created | Detach and drop child table |
| Data backfill | Reverse backfill script |
| Column renamed | Reverse expand-contract |

**Constraint**: audit_log partitions are **never rolled back** — they are the legal audit trail.

---

## CI/CD Integration

```yaml
# .github/workflows/db-migrate.yml (excerpt)
- name: Run Alembic migrations
  run: |
    alembic upgrade head
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}

- name: Verify schema version
  run: |
    alembic current
    alembic check   # fails if autogenerate detects drift
```

---

## Developer Workflow

```bash
# Create a new revision (autogenerate from model diff)
alembic revision --autogenerate -m "add_nationality_to_persons"

# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history --verbose
```

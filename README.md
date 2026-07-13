?# OurFamRoots

A genealogy platform for building, exploring, and collaborating on family trees. Built with FastAPI, React, PostgreSQL, and Redis.

---

## Table of Contents

- [OurFamRoots](#ourfamroots)
  - [Table of Contents](#table-of-contents)
  - [Tech Stack](#tech-stack)
  - [Prerequisites](#prerequisites)
    - [Local development](#local-development)
    - [Outside Docker (optional)](#outside-docker-optional)
    - [Staging / Production](#staging--production)
  - [Local Deployment](#local-deployment)
    - [1. Clone and configure](#1-clone-and-configure)
    - [2. Start core services](#2-start-core-services)
    - [3. Run database migrations](#3-run-database-migrations)
    - [4. Seed initial data](#4-seed-initial-data)
      - [System accounts](#system-accounts)
      - [Demo family tree (optional)](#demo-family-tree-optional)
    - [5. Access the app](#5-access-the-app)
      - [Registration notes](#registration-notes)
      - [Tree views](#tree-views)
      - [Propose Changes to a Shared Tree](#propose-changes-to-a-shared-tree)
      - [Admin Dashboard](#admin-dashboard)
    - [6. Optional: monitoring stack](#6-optional-monitoring-stack)
    - [Stopping the stack](#stopping-the-stack)
    - [Running tests](#running-tests)
      - [Backend](#backend)
      - [Frontend](#frontend)
  - [Staging Deployment](#staging-deployment)
    - [1. Configure staging secrets](#1-configure-staging-secrets)
    - [2. Deploy to staging](#2-deploy-to-staging)
    - [3. Run staging migrations](#3-run-staging-migrations)
    - [4. Seed staging accounts](#4-seed-staging-accounts)
  - [Production Deployment](#production-deployment)
    - [Production Prerequisites](#production-prerequisites)
    - [1. Configure secrets](#1-configure-secrets)
    - [2. Build and push images](#2-build-and-push-images)
    - [3. Deploy with Helm](#3-deploy-with-helm)
    - [4. Verify the deployment](#4-verify-the-deployment)
    - [Rolling back](#rolling-back)
    - [CI/CD pipeline](#cicd-pipeline)
  - [GCP Deployment (Free Trial)](#gcp-deployment-free-trial)
    - [Architecture on GCP](#architecture-on-gcp)
    - [GCP Prerequisites](#gcp-prerequisites)
    - [1. Create GCP project and enable APIs](#1-create-gcp-project-and-enable-apis)
    - [2. Create infrastructure](#2-create-infrastructure)
    - [3. Push images to Artifact Registry](#3-push-images-to-artifact-registry)
    - [4. Store secrets in Secret Manager](#4-store-secrets-in-secret-manager)
    - [5. Deploy to Cloud Run](#5-deploy-to-cloud-run)
    - [6. Run migrations and seed data](#6-run-migrations-and-seed-data)
    - [7. Access the app](#7-access-the-app)
    - [Estimated trial costs](#estimated-trial-costs)
    - [Tearing down](#tearing-down)
  - [Port Reference](#port-reference)
  - [Troubleshooting](#troubleshooting)
    - [Photos / avatars return 500 through `/s3/` on the docker-compose VM deployment](#photos--avatars-return-500-through-s3-on-the-docker-compose-vm-deployment)

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend API | FastAPI (Python 3.11), Uvicorn, Celery |
| Frontend | React 18, TypeScript, Vite, TanStack Query, Zustand, ReactFlow, Tailwind CSS |
| Database | PostgreSQL 15 |
| Cache / Queue | Redis 7 |
| Object Storage | MinIO (local) / AWS S3 (staging & production) |
| Migrations | Alembic |
| Email | Gmail SMTP (all environments) |
| Monitoring | Prometheus, Grafana, Loki, Promtail |
| Production infra | Kubernetes, Helm, GitHub Actions (blue/green deploy) |

---

## Prerequisites

### Local development

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Docker Compose v2)
- Git

### Outside Docker (optional)

- Python 3.11+
- Node.js 20+

### Staging / Production

- Kubernetes cluster (1.28+)
- Helm 3.14+
- `kubectl` configured for your cluster
- GitHub repository with Actions enabled
- AWS account (S3) or equivalent object storage
- Container registry (defaults use GitHub Container Registry)

---

## Local Deployment

All services run via Docker Compose. Everything — database, cache, object storage, API, worker, and frontend — starts with a single command.

### 1. Clone and configure

```bash
git clone <repo-url>
cd ourfamroots
```

Copy the backend environment file:

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in the required values:

```env
# ── Required: generate with: openssl rand -hex 64 ──────────────────────────
JWT_SECRET_KEY=<your-64-char-hex-secret>

# ── Required: PostgreSQL credentials ───────────────────────────────────────
POSTGRES_PASSWORD=<choose-a-local-password>

# ── Required: MinIO credentials (local S3) ─────────────────────────────────
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# ── Required: Gmail SMTP (for email verification and password reset) ────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<your-gmail-address>
SMTP_PASSWORD=<your-gmail-app-password>
EMAIL_FROM=<your-gmail-address>

# ── Optional: Super Administrator ──────────────────────────────────────────
# Set this to the email of the user who should have full site control
# (view all trees/users, toggle maintenance mode, send broadcast emails).
# SUPER_ADMIN_EMAIL=admin@example.com

# ── Pre-filled — change only if needed ─────────────────────────────────────
DEFAULT_TENANT_SLUG=ourfamroots-system
S3_PUBLIC_URL=http://localhost:7002
```

**Gmail App Password** — Do not use your Google account password. Go to
[Google Account → Security → App passwords](https://myaccount.google.com/apppasswords),
enable 2-Step Verification, then create a new app password for OurFamRoots and
paste the 16-character result into `SMTP_PASSWORD`.

**`JWT_SECRET_KEY`** — Must be at least 32 characters. Generate a strong value with:

```bash
openssl rand -hex 64
```

**`DEFAULT_TENANT_SLUG`** — OurFamRoots supports multiple **namespaces** (isolated
spaces, each with its own Admin/Standard/Auditor roles). Exactly one namespace is
flagged `is_global` and is where every new registration lands by default — this
setting identifies that namespace by slug. A Super Admin can create additional
namespaces (Admin Dashboard → Namespaces) and invite Global-namespace users into
them; accepting an invitation transfers the user's account into that namespace
and forces a re-login. Changing this slug after data is seeded requires a data migration.

**`S3_PUBLIC_URL`** — Presigned MinIO download URLs are rewritten to this host before being
returned to the browser. The internal `minio:9000` hostname is unreachable outside Docker,
so this must point to the externally reachable MinIO API port (`http://localhost:7002` locally).

**`SUPER_ADMIN_EMAIL`** — (Optional) The email address of the Super Administrator.
This user automatically receives the `SUPER_ADMIN` role on login and gets:

- **Full visibility** — can see all trees and all users across every namespace
- **Namespace management** — can create additional namespaces and invite Global-namespace users into them (Admin Dashboard → Namespaces)
- **Maintenance mode** — can toggle the site to "Under Construction" with a custom message (Admin Dashboard → Site Settings)
- **Broadcast email** — can compose and send emails to all users or selected recipients (Admin Dashboard → Broadcast), with full history tracking
- Users can unsubscribe from broadcast emails in Settings → Notifications

### 2. Start core services

```bash
docker compose up -d
```

This starts:

| Service | Description | Port |
| --- | --- | --- |
| **PostgreSQL** | Primary database | 7000 |
| **Redis** | Cache and Celery broker | 7001 |
| **MinIO** (S3 API) | Local object storage for media uploads | 7002 |
| **MinIO Console** | Web UI for browsing buckets | 7003 |
| **Backend API** | FastAPI + Uvicorn (hot reload) | 7004 |
| **Celery worker** | Background task processor (media, email) | — |
| **Flower** | Celery task monitor | 7005 |
| **Frontend** | Vite dev server (hot reload) | 7006 |

Wait until all services are healthy before proceeding:

```bash
docker compose ps
```

All services should show `healthy` or `running`.

### 3. Run database migrations

```bash
docker compose run --rm migrate
```

This applies the full Alembic migration history, creating all tables, enums, indexes, and triggers.

> Run once on first setup, and again after pulling changes that include new migrations.

### 4. Seed initial data

#### System accounts

After running migrations on a fresh database, create the built-in system accounts:

```bash
python backend/scripts/seed_users.py
```

This creates the following accounts in the `ourfamroots-system` tenant:

| Email | Password | Role |
| --- | --- | --- |
| `admin@ourfamroots.app` | `Admin@FR2024!` | ADMIN |
| `user@ourfamroots.app` | `User@FR2024!` | STANDARD |
| `auditor@ourfamroots.app` | `Auditor@FR2024!` | AUDITOR |

> After a full reset (`docker compose down -v`), re-run migrations then re-run the seed script.

#### Demo family tree (optional)

To load a ready-made family tree that demonstrates the full 8-generation ancestry fan chart,
copy the seed file into the database container and run it:

```bash
# Copy seed file into the running container
docker compose cp seed_dynasty_8gen.sql db:/seed_dynasty_8gen.sql

# Run it (attaches the tree to the first registered user)
docker compose exec db psql -U postgres ourfamroots -f /seed_dynasty_8gen.sql
```

This seeds **The Mitchell Dynasty** — 255 persons across 8 generations, from William James
Mitchell (b. 1990) back to Georgian ancestors (b. ~1783). To view all 8 rings:

1. Log in and open the tree.
2. Switch to **Ancestry Fan Chart** view (◎ button in the toolbar).
3. Click **Set as Focus** on William James Mitchell.

A smaller 4-generation Smith family tree is also available:

```bash
docker compose cp seed_family.sql db:/seed_family.sql
docker compose exec db psql -U postgres ourfamroots -f /seed_family.sql
```

### 5. Access the app

| Service | URL | Notes |
| --- | --- | --- |
| Frontend | <http://localhost:7006> | Use a seed account or register |
| Backend API | <http://localhost:7004> | REST API |
| Swagger UI | <http://localhost:7004/docs> | Interactive API docs |
| ReDoc | <http://localhost:7004/redoc> | API reference |
| Flower | <http://localhost:7005> | Celery task monitor |
| MinIO Console | <http://localhost:7003> | `minioadmin` / `minioadmin` |

#### Registration notes

- There is no "Organisation ID" field — all new users join the shared `ourfamroots-system` tenant automatically.
- `POST /auth/register` returns `204 No Content`. No JWT is issued at registration time.
- A verification email is sent immediately. The account cannot log in until the email link is clicked.
- To resend the verification email: `POST /api/v1/auth/resend-verification`.
- Admins can manually verify an account via the Admin Dashboard or `POST /api/v1/admin/users/{id}/verify`.
- Forgot password returns `403 account-not-verified` if the email has not been verified yet.

#### Tree views

The default view when opening any tree is the **Ancestor chart** (focus person at the bottom,
ancestors climbing upward). Use the toolbar to switch between all available layouts:

| Button | Mode | Description |
| --- | --- | --- |
| 📊 | Generation sort | Top-to-bottom sorted by generation |
| ↕ | Vertical | Multi-marriage-aware top-to-bottom layout |
| ↔ | Horizontal | Left-to-right generation layout |
| ↑ | Ancestor | Focus at bottom, ancestors above (default) |
| ↓ | Descendant | Focus at top, descendants below |
| 👨‍👩‍👧 | Descendants + Spouses | Descendants with spouses kept adjacent going downward |
| 👴 | Ancestors + Spouses | Ancestors with spouses kept adjacent going upward |
| ◑ | Fan chart | 180° semicircular fan |
| ◎ | Ancestry fan chart | Full SVG fan chart — up to 8 rings with hover tooltips |
| ⊢ | Pedigree | Horizontal binary ancestor tree |
| 🗜 | Compact view | Tight family-tree layout, minimises spacing gaps |

Hovering over any wedge in the fan chart shows a tooltip with the person's full name,
relationship label (e.g. "3× Great-grandparent"), and birth–death years.

**Focus filters:** Right-click any person card → **Focus** to set them as the focus person.
Ancestor, Descendant, and Descendants+Spouses layouts all root the tree from that person.

**Compact Descendants:** While in **Descendants + Spouses** mode, **Shift+click** the Compact
button to tighten spacing and eliminate gaps between descendant lines. Both toolbar buttons
glow simultaneously when active. This also works in reverse — Shift+click Descendants+Spouses
while Compact is active to apply the same combined effect.

#### Timeline View

Open via **Extensions 🧩** dropdown → **Timeline**. Each person appears as a coloured horizontal
bar spanning their birth to death year (or present day for living members).

- **Scroll / pan:** Scroll the mouse wheel or drag vertically to move through the list of people.
  Drag horizontally to pan across the time axis.
- **Sticky year bar:** Decade labels remain pinned to the top as you scroll — you always know
  which year range is in view.
- **Status bar:** A fixed bottom bar shows live counts: how many members are visible and which
  row range is currently in the viewport.
- **Zoom:** Use the **+** / **−** buttons to adjust pixels-per-year. Zoom in for century-level
  detail, zoom out to see the whole family at once.
- **No birth year:** People without a birth year appear in a separate section below the timeline bars.
- **Virtual rendering:** Only rows near the viewport are rendered, so trees with hundreds of
  members stay smooth.

#### View Styles & Extensions

Two dropdown menus at the end of the toolbar provide alternate rendering:

**🎨 View Styles** (built-in):

| Style | Description |
| --- | --- |
| Default | Standard modern card view |
| Heritage | Vintage parchment cards with serif text, sepia photo filter, orthogonal (right-angle) connecting lines |

**🧩 Extensions** (plug-in views):

| Extension | Description |
| --- | --- |
| Timeline | Horizontal year-axis view — each person is a coloured bar from birth to death |
| Grid Cards | Sortable card grid (example extension) |

View Styles are independent of the colour theme — you can use Heritage with Dark theme, for example.

#### Heritage View — Union Line Styles

Heritage view uses orthogonal (right-angle step) paths for connecting lines, but all union
visual rules from the Default view apply:

| Union type | Line style |
| --- | --- |
| Marriage | Double amber line |
| Marriage (divorced) | Double dashed grey line |
| Partnership | Single solid green line |
| Cohabitation | Single dashed indigo line |
| Unknown | Single dotted grey line |

Ordinal labels ("1st Marriage", "2nd Marriage") appear on multiple same-type unions, the same
as in Default view. Custom labels set via double-click are preserved across view styles.

#### PDF Export

From any tree view, click **Export → PDF** to capture the current canvas as an image-based PDF.

- **What-you-see-is-what-you-get:** The PDF captures the viewport exactly — zoom, pan, and
  legend placement are all preserved.
- **Legend positioning:** Drag the legend to any corner *before* exporting. It appears at
  exactly that position in the PDF.
- **Timeline export:** When exporting the Timeline view, the controls bar and bottom status bar
  are automatically hidden. The PDF title is set to the tree name for a clean output.
- **View styles:** Heritage and other view styles export exactly as rendered on screen.

#### Extension Plugin System

View extensions live in `frontend/src/extensions/views/`. Each extension is a folder
with an `index.ts` that exports a `ViewPlugin` object. The registry auto-discovers all
extensions via `import.meta.glob` at build time.

```text
frontend/src/extensions/views/
  registry.ts           ← auto-discovery + ViewPlugin interface
  default/index.ts      ← built-in: standard view
  heritage/             ← built-in: vintage parchment style
    index.ts
    HeritagePersonNode.tsx
  timeline/index.ts     ← extension: horizontal timeline
  ext1/                 ← extension: grid cards (example)
    index.ts
    ExampleCanvas.tsx
```

**To add a new view:** create a folder, add `index.ts` exporting a `ViewPlugin`, restart
the dev server. No core files need to change. See `frontend/src/extensions/views/README.md`.

**To remove a view:** delete the folder and restart.

Backend extension hooks (for views needing server-side support) go in
`backend/extensions/views/`. Currently unused — all views are frontend-only.

#### Import / Export (.ofr)

OurFamRoots uses a native `.ofr` backup format (JSON-based) for tree import and export.
The format preserves all person data including:

| Field | Description |
| --- | --- |
| `display_given_name` / `display_surname` | Name fields |
| `sex` | MALE, FEMALE, OTHER, UNKNOWN |
| `is_living` / `is_deceased` | Living status |
| `photo_url` | Profile photo URL |
| `birth_date` / `death_date` | Full ISO dates (YYYY-MM-DD) |
| `birth_year` / `death_year` | Year-only fallback when full date is unknown |
| `facebook_handle` / `x_handle` / `linkedin_handle` | Social profile handles |

Family groups also preserve `custom_label` (user-defined union labels) and `union_type`.

**Export:** From the tree toolbar, click **Export as .ofr** to download the full tree backup.

**Import:** From the dashboard, click **Import tree** and upload a `.ofr` file. All persons
are re-created with new UUIDs and the importing user becomes the tree owner.

#### Propose Changes to a Shared Tree

On a **globally-shared** tree, Editor-level members can't edit the live tree directly — they
propose changes for the owner to review instead:

1. **Propose changes** — clones the tree into a private draft only you can see. Edit it with
   the normal person/relationship tools; nothing touches the live tree yet.
2. **Post** — submits the draft to the tree owner for review. The owner gets an email + in-app
   notification.
3. **Review** — the owner reviews the proposal two ways:
   - A diff modal listing added/removed/modified persons, connecting-member relationships
     (e.g. "child of Jane Doe"), and a raw JSON view — reachable from the notification or the
     tree's **Pending proposals** button.
   - **View in tree** — opens the draft itself on the real tree canvas (same pan/zoom/expand
     as any tree), with added persons highlighted green and modified persons amber, plus an
     Approve/Deny bar in place of the normal toolbar.
4. **Approve / Deny** — approving merges the draft's persons and relationships onto the live
   tree (matched persons keep their id; new persons are adopted; removed persons are
   soft-deleted). Denying discards the draft. Either way the requester is notified.

**Reverting an approval (Super Admin only):** every approval captures a full snapshot of the
tree immediately beforehand. If a Super Admin needs to undo one — e.g. a bad merge — they can
click **Revert** on that approval's entry in the tree's **History** log. This restores persons
and family groups to exactly their pre-approval state; note that it necessarily undoes *any*
edits made after the approval too, not just that one change, since it's a full snapshot
restore rather than a surgical undo.

#### Admin Dashboard

Accessible to ADMIN-role accounts, scoped to their own namespace (a Super Admin
sees and manages every namespace):

- **Users** — manually verify/unverify, deactivate/reactivate (email notifications
  sent on each action), search/filter/sort, and (Super Admin only) filter by namespace
- **Permission Groups** — reusable bundles of tree access at a given role
  (Viewer/Editor); grant to individual members, a linked User Group, or make
  global (applies to every user in the namespace)
- **User Groups** — reusable collections of users; link a User Group to a
  Permission Group so its members inherit access immediately, or use it for
  bulk role assignment
- **Subscriptions** — Free/Premium plans that grant members access to a set of
  tree filters, with optional expiry
- **Namespaces** (Super Admin only) — create additional namespaces and invite
  Global-namespace users into them
- **Activity feed** — every admin action, login event, and (for Auditor/Super
  Admin) cross-namespace activity, searchable and exportable to CSV

### 6. Optional: monitoring stack

Start Prometheus, Grafana, Loki, and log shipping alongside the core stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

| Service | URL | Credentials |
| --- | --- | --- |
| Grafana | <http://localhost:7009> | `admin` / `admin` |
| Prometheus | <http://localhost:7007> | — |
| Alertmanager | <http://localhost:7008> | — |
| Loki | <http://localhost:7010> | — |

Grafana dashboards are provisioned automatically. Navigate to **Dashboards → API Overview**.

To set a custom Grafana password:

```bash
GRAFANA_PASSWORD=yourpassword \
  docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

### Stopping the stack

```bash
# Stop without removing data
docker compose down

# Full reset — removes all volumes and data
docker compose down -v
```

---

### Running tests

#### Backend

Unit tests (no Docker or external services required):

```bash
cd backend
pip install -r requirements/test.txt
pytest tests/unit -n auto --tb=short -q
```

Integration tests (requires PostgreSQL and Redis — use `docker compose up -d db redis`):

```bash
pytest tests/integration -n 2 --tb=short -q
```

Most of `tests/integration` runs against an in-memory fake session (no real DB needed). One
module — `test_change_request_revert.py`, covering the propose/approve/revert flow's raw SQL —
needs a real, migrated Postgres database via `TEST_DATABASE_URL`, and skips itself if that
isn't set:

```bash
docker compose exec db psql -U postgres -c "CREATE DATABASE ourfamroots_test;"
docker compose run --rm \
  -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/ourfamroots_test \
  migrate

TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:7000/ourfamroots_test \
  pytest tests/integration/test_change_request_revert.py -v
```

CI provisions and migrates this database automatically for every run (see `ci.yml`'s
`backend-integration` job).

Security tests:

```bash
pytest tests/security -v
```

All backend tests with coverage:

```bash
# Unit suite — must reach 90% on non-infrastructure code
pytest tests/unit --cov=src --cov-report=term-missing --cov-fail-under=90

# Integration suite — must reach 65% on non-infrastructure code
pytest tests/integration --cov=src --cov-report=term-missing --cov-fail-under=65
```

> Coverage is measured against the `src/` tree using `.coveragerc`, which omits
> infrastructure adapters (DB session, S3, email, repositories) that require live
> services. The unit suite enforces the high bar (≥ 90%); the integration suite
> enforces a lower bar (≥ 65%) because it focuses on HTTP contract testing rather
> than exhaustive domain coverage.

#### Frontend

Unit tests:

```bash
cd frontend
npm ci
npm test
```

E2E tests (requires the full stack via `docker compose up -d`):

```bash
npx playwright install --with-deps chromium
npx playwright test --project=chromium
```

---

## Staging Deployment

Staging uses the same Helm chart as production but points to a separate namespace,
separate secrets, and a dedicated S3 bucket. The `develop` branch deploys to staging
automatically via CI.

### 1. Configure staging secrets

```bash
kubectl create namespace ourfamroots-staging

kubectl create secret generic ourfamroots-secrets \
  --namespace ourfamroots-staging \
  --from-literal=DB_PASSWORD='<staging-postgres-password>' \
  --from-literal=REDIS_PASSWORD='<staging-redis-password>' \
  --from-literal=JWT_SECRET='<64-char-hex-secret>' \
  --from-literal=AWS_ACCESS_KEY_ID='<key-id>' \
  --from-literal=AWS_SECRET_ACCESS_KEY='<secret-key>' \
  --from-literal=SMTP_PASSWORD='<gmail-app-password>' \
  --from-literal=SENTRY_DSN='<sentry-dsn>'
```

Add the corresponding **GitHub Actions secrets** (prefix with `STG_` to distinguish from production):

| Secret | Description |
| --- | --- |
| `STG_KUBE_CONFIG` | Base64-encoded kubeconfig for the staging cluster |
| `STG_DB_PASSWORD` | PostgreSQL password |
| `STG_REDIS_PASSWORD` | Redis password |
| `STG_JWT_SECRET` | JWT signing key |
| `STG_S3_BUCKET` | Staging S3 bucket name |
| `STG_S3_REGION` | AWS region |
| `STG_AWS_ACCESS_KEY_ID` | AWS access key |
| `STG_AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `STG_SMTP_USER` | Gmail address for staging emails |
| `STG_SMTP_PASSWORD` | Gmail App Password |
| `STG_EMAIL_FROM` | From address for staging emails |
| `STG_CORS_ORIGINS` | `["https://staging.ourfamroots.example.com"]` |

### 2. Deploy to staging

Staging can be deployed manually or by CI on push to `develop`:

```bash
export REGISTRY=ghcr.io
export ORG=your-org
export TAG=$(git rev-parse --short HEAD)

helm upgrade --install ourfamroots-staging ./helm/ourfamroots \
  --namespace ourfamroots-staging \
  --set image.org=$ORG \
  --set image.tag=$TAG \
  --set ingress.host=staging.ourfamroots.example.com \
  --set ingress.apiHost=api.staging.ourfamroots.example.com \
  --set env.ENVIRONMENT=staging \
  --set env.DEFAULT_TENANT_SLUG=ourfamroots-system \
  --wait
```

### 3. Run staging migrations

```bash
kubectl run migrate \
  --image=ghcr.io/$ORG/ourfamroots/api:$TAG \
  --restart=Never \
  --namespace=ourfamroots-staging \
  --env="DATABASE_URL=<staging-database-url>" \
  -- alembic upgrade head

kubectl wait --for=condition=complete pod/migrate -n ourfamroots-staging --timeout=120s
kubectl delete pod migrate -n ourfamroots-staging
```

### 4. Seed staging accounts

```bash
kubectl run seed \
  --image=ghcr.io/$ORG/ourfamroots/api:$TAG \
  --restart=Never \
  --namespace=ourfamroots-staging \
  --env="DATABASE_URL=<staging-database-url>" \
  -- python scripts/seed_users.py

kubectl wait --for=condition=complete pod/seed -n ourfamroots-staging --timeout=60s
kubectl delete pod seed -n ourfamroots-staging
```

---

## Production Deployment

Production runs on Kubernetes with blue/green deployments managed by GitHub Actions.
Images are built by CI and pushed to GitHub Container Registry.

### Production Prerequisites

- A Kubernetes cluster with an nginx ingress controller and `cert-manager` installed
- `kubectl` pointing at your cluster
- Helm 3.14+
- DNS records pointing your domain to the ingress controller's external IP

### 1. Configure secrets

```bash
kubectl create namespace ourfamroots

kubectl create secret generic ourfamroots-secrets \
  --namespace ourfamroots \
  --from-literal=DB_PASSWORD='<postgres-password>' \
  --from-literal=REDIS_PASSWORD='<redis-password>' \
  --from-literal=JWT_SECRET='<64-char-hex-secret>' \
  --from-literal=AWS_ACCESS_KEY_ID='<key-id>' \
  --from-literal=AWS_SECRET_ACCESS_KEY='<secret-key>' \
  --from-literal=SMTP_PASSWORD='<gmail-app-password>' \
  --from-literal=SENTRY_DSN='<sentry-dsn>'
```

Generate a strong JWT secret:

```bash
openssl rand -hex 64
```

**GitHub Actions secrets** — add the following in Settings → Secrets → Actions:

| Secret | Description |
| --- | --- |
| `KUBE_CONFIG` | Base64-encoded kubeconfig for your cluster |
| `DB_PASSWORD` | PostgreSQL password |
| `REDIS_PASSWORD` | Redis password |
| `JWT_SECRET` | JWT signing key (≥ 32 characters) |
| `DEFAULT_TENANT_SLUG` | Shared tenant slug (e.g. `ourfamroots-system`) |
| `S3_BUCKET` | S3 bucket name |
| `S3_REGION` | AWS region (e.g. `us-east-1`) |
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_USER` | Gmail address for transactional email |
| `SMTP_PASSWORD` | Gmail App Password |
| `EMAIL_FROM` | From address in outbound email |
| `CORS_ORIGINS` | JSON array, e.g. `["https://ourfamroots.example.com"]` |
| `SENTRY_DSN` | Sentry DSN (optional) |
| `GRAFANA_PASSWORD` | Grafana admin password (optional) |

### 2. Build and push images

CI does this automatically on every push to `main`. To build manually:

```bash
export REGISTRY=ghcr.io
export ORG=your-org
export TAG=$(git rev-parse --short HEAD)

echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_ACTOR --password-stdin

docker build --target runtime -t $REGISTRY/$ORG/ourfamroots/api:$TAG ./backend
docker push $REGISTRY/$ORG/ourfamroots/api:$TAG

docker build -t $REGISTRY/$ORG/ourfamroots/frontend:$TAG ./frontend
docker push $REGISTRY/$ORG/ourfamroots/frontend:$TAG
```

### 3. Deploy with Helm

```bash
helm upgrade --install ourfamroots ./helm/ourfamroots \
  --namespace ourfamroots \
  --set image.org=your-org \
  --set image.tag=$TAG \
  --set ingress.host=ourfamroots.example.com \
  --set ingress.apiHost=api.ourfamroots.example.com \
  --wait
```

Run migrations on first install:

```bash
kubectl run migrate \
  --image=ghcr.io/your-org/ourfamroots/api:$TAG \
  --restart=Never \
  --namespace=ourfamroots \
  --env="DATABASE_URL=<your-database-url>" \
  -- alembic upgrade head

kubectl wait --for=condition=complete pod/migrate -n ourfamroots --timeout=120s
kubectl delete pod migrate -n ourfamroots
```

Seed system accounts on first install:

```bash
kubectl run seed \
  --image=ghcr.io/your-org/ourfamroots/api:$TAG \
  --restart=Never \
  --namespace=ourfamroots \
  --env="DATABASE_URL=<your-database-url>" \
  -- python scripts/seed_users.py

kubectl wait --for=condition=complete pod/seed -n ourfamroots --timeout=60s
kubectl delete pod seed -n ourfamroots
```

### 4. Verify the deployment

```bash
# Check pod health
kubectl get pods -n ourfamroots

# Check API health endpoint
curl https://api.ourfamroots.example.com/health
# Expected: {"status": "ok"}

# Check rollout status
kubectl rollout status deployment/api-blue -n ourfamroots
kubectl rollout status deployment/frontend-blue -n ourfamroots
```

### Rolling back

```bash
# Roll back the Helm release
helm rollback ourfamroots -n ourfamroots

# Or roll back the Kubernetes deployment directly
kubectl rollout undo deployment/api-blue -n ourfamroots
```

---

### CI/CD pipeline

| Branch | Trigger | Jobs run |
| --- | --- | --- |
| Any PR | Push | Tests + coverage gate (no deploy) |
| `develop` | Push | Tests + coverage gate + build + staging deploy |
| `main` | Push | Tests + coverage gate + build + production deploy |

**Pipeline steps:**

1. **Backend unit tests** — pytest, no external services needed. Coverage must be **≥ 90%**.
2. **Backend integration tests** — pytest with live PostgreSQL + Redis. Coverage must be **≥ 65%**.
3. **Backend security tests** — pytest + Bandit static analysis.
4. **Frontend unit tests** — Vitest with coverage.
5. **E2E tests** — Playwright (Chromium) against a live stack.
6. **Coverage gate** — blocks merge if unit backend < 90% or frontend unit tests fail.
7. **Build & push** — Docker images tagged with the commit SHA.
8. **Blue/green deploy** — deploys to the inactive slot, runs a smoke test, then switches traffic.

> The integration test coverage threshold (65%) is intentionally lower than the unit
> threshold (90%) because integration tests verify HTTP contracts, not domain logic.
> The `.coveragerc` omits infrastructure adapters from measurement in both suites.

---

## GCP Deployment (Free Trial)

Google Cloud's **$300 free trial credit** (valid for 90 days) is enough to run
OurFamRoots on a minimal Cloud Run + Cloud SQL + Cloud Storage stack for the full
trial period.

> **Activate the trial:** [cloud.google.com/free](https://cloud.google.com/free).
> A credit card is required for identity verification but you will **not** be charged
> until you manually upgrade to a paid account.

### Architecture on GCP

| Local service | GCP equivalent |
| --- | --- |
| Backend API (Docker) | Cloud Run service |
| Frontend (Docker) | Cloud Run service |
| Celery worker (Docker) | Cloud Run service |
| PostgreSQL | Cloud SQL for PostgreSQL 15 |
| Redis | Memorystore for Redis |
| MinIO (object storage) | Cloud Storage (via S3-compatible HMAC API) |
| Docker images | Artifact Registry |
| `backend/.env` secrets | Secret Manager |

### GCP Prerequisites

- [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed
  and initialised (`gcloud init`)
- Docker Desktop running locally
- A Google account with the free trial activated

### 1. Create GCP project and enable APIs

```bash
# Replace PROJECT_ID with a globally unique identifier, e.g. ourfamroots-2025
gcloud projects create PROJECT_ID --name="OurFamRoots"
gcloud config set project PROJECT_ID

# Link the free-trial billing account
gcloud billing projects link PROJECT_ID \
  --billing-account=$(gcloud billing accounts list \
      --format="value(name)" --filter="open=true" | head -1)

# Enable all required APIs
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  vpcaccess.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com
```

### 2. Create infrastructure

Export these variables once — every subsequent command reuses them:

```bash
export PROJECT_ID=ourfamroots-2025       # your GCP project ID
export REGION=us-central1                # region closest to your users
export DB_INSTANCE=ourfamroots-db
export DB_NAME=ourfamroots
export DB_USER=ourfamroots
export DB_PASS=$(openssl rand -hex 16)   # save this — you'll need it later
export BUCKET=ourfamroots-media-$PROJECT_ID
export REDIS_INSTANCE=ourfamroots-cache
export AR_REPO=ourfamroots
export VPC_CONNECTOR=ourfamroots-vpc
```

**Cloud SQL (PostgreSQL 15):**

```bash
gcloud sql instances create $DB_INSTANCE \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$REGION \
  --storage-size=10GB \
  --storage-auto-increase \
  --no-backup

gcloud sql databases create $DB_NAME --instance=$DB_INSTANCE

gcloud sql users create $DB_USER \
  --instance=$DB_INSTANCE \
  --password=$DB_PASS
```

> `db-f1-micro` is the smallest tier (1 shared vCPU, 614 MB RAM). Sufficient for
> development and low-traffic use — costs ~$8/month from trial credit.

**Cloud Storage bucket (replaces MinIO):**

```bash
gcloud storage buckets create gs://$BUCKET \
  --location=$REGION \
  --uniform-bucket-level-access
```

Cloud Storage is accessed via its S3-compatible XML API using HMAC keys — no code
changes required. Generate a key for the default Compute service account:

```bash
export SA="$(gcloud projects describe $PROJECT_ID \
  --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

gcloud storage hmac create $SA --project=$PROJECT_ID
# ── Note the printed `accessId` and `secret` — store them as HMAC_KEY / HMAC_SECRET
```

**Memorystore for Redis:**

```bash
gcloud redis instances create $REDIS_INSTANCE \
  --size=1 \
  --region=$REGION \
  --redis-version=redis_7_0 \
  --tier=basic
```

> Takes 5–10 minutes to provision. The instance runs inside the default VPC, so Cloud
> Run needs a serverless VPC connector to reach it.

**Serverless VPC connector (Cloud Run → Redis):**

```bash
gcloud compute networks vpc-access connectors create $VPC_CONNECTOR \
  --region=$REGION \
  --range=10.8.0.0/28
```

**Artifact Registry repository:**

```bash
gcloud artifacts repositories create $AR_REPO \
  --repository-format=docker \
  --location=$REGION
```

### 3. Push images to Artifact Registry

```bash
export IMAGE_BASE=$REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO
export TAG=$(git rev-parse --short HEAD)

# Authenticate Docker with Artifact Registry
gcloud auth configure-docker $REGION-docker.pkg.dev

# Build and push the backend image
docker build --target runtime -t $IMAGE_BASE/api:$TAG ./backend
docker push $IMAGE_BASE/api:$TAG

# Build and push the frontend image
docker build -t $IMAGE_BASE/frontend:$TAG ./frontend
docker push $IMAGE_BASE/frontend:$TAG
```

### 4. Store secrets in Secret Manager

```bash
# JWT signing key
openssl rand -hex 64 | gcloud secrets create JWT_SECRET_KEY --data-file=-

# Database password (the value exported in step 2)
echo -n "$DB_PASS" | gcloud secrets create DB_PASSWORD --data-file=-

# HMAC credentials for Cloud Storage (S3-compatible access)
echo -n "<HMAC_KEY>"    | gcloud secrets create GCS_HMAC_KEY    --data-file=-
echo -n "<HMAC_SECRET>" | gcloud secrets create GCS_HMAC_SECRET --data-file=-

# Gmail SMTP credentials
echo -n "<your-gmail-address>"      | gcloud secrets create SMTP_USER     --data-file=-
echo -n "<your-gmail-app-password>" | gcloud secrets create SMTP_PASSWORD --data-file=-
```

Grant the Compute service account access to read all secrets and connect to Cloud SQL:

```bash
for SECRET in JWT_SECRET_KEY DB_PASSWORD GCS_HMAC_KEY GCS_HMAC_SECRET \
              SMTP_USER SMTP_PASSWORD; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretAccessor"
done

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" \
  --role="roles/cloudsql.client"

gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member="serviceAccount:$SA" \
  --role="roles/storage.objectAdmin"
```

### 5. Deploy to Cloud Run

Fetch the values needed for environment variables:

```bash
export REDIS_HOST=$(gcloud redis instances describe $REDIS_INSTANCE \
  --region=$REGION --format="value(host)")

export CLOUD_SQL_CONN="$PROJECT_ID:$REGION:$DB_INSTANCE"

# Cloud Storage S3-compatible endpoint
export S3_ENDPOINT=https://storage.googleapis.com
export S3_PUBLIC_URL=https://storage.googleapis.com/$BUCKET
```

**Deploy the backend API:**

```bash
gcloud run deploy ourfamroots-api \
  --image=$IMAGE_BASE/api:$TAG \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --add-cloudsql-instances=$CLOUD_SQL_CONN \
  --vpc-connector=$VPC_CONNECTOR \
  --vpc-egress=private-ranges-only \
  --set-env-vars="ENVIRONMENT=production" \
  --set-env-vars="DEFAULT_TENANT_SLUG=ourfamroots-system" \
  --set-env-vars="DATABASE_URL=postgresql+asyncpg://$DB_USER:$(gcloud secrets versions access latest --secret=DB_PASSWORD)@/$DB_NAME?host=/cloudsql/$CLOUD_SQL_CONN" \
  --set-env-vars="REDIS_URL=redis://$REDIS_HOST:6379/0" \
  --set-env-vars="S3_BUCKET=$BUCKET,S3_REGION=$REGION" \
  --set-env-vars="S3_ENDPOINT_URL=$S3_ENDPOINT,S3_PUBLIC_URL=$S3_PUBLIC_URL" \
  --set-env-vars="SMTP_HOST=smtp.gmail.com,SMTP_PORT=587" \
  --set-secrets="JWT_SECRET_KEY=JWT_SECRET_KEY:latest" \
  --set-secrets="AWS_ACCESS_KEY_ID=GCS_HMAC_KEY:latest" \
  --set-secrets="AWS_SECRET_ACCESS_KEY=GCS_HMAC_SECRET:latest" \
  --set-secrets="SMTP_USER=SMTP_USER:latest,SMTP_PASSWORD=SMTP_PASSWORD:latest" \
  --min-instances=0 \
  --max-instances=3 \
  --memory=512Mi \
  --cpu=1
```

> The backend uses boto3's S3 client. Pointing `S3_ENDPOINT_URL` at
> `https://storage.googleapis.com` and supplying HMAC credentials makes it talk to
> Cloud Storage with no code changes.

**Deploy the Celery worker:**

```bash
gcloud run deploy ourfamroots-worker \
  --image=$IMAGE_BASE/api:$TAG \
  --region=$REGION \
  --platform=managed \
  --no-allow-unauthenticated \
  --add-cloudsql-instances=$CLOUD_SQL_CONN \
  --vpc-connector=$VPC_CONNECTOR \
  --vpc-egress=private-ranges-only \
  --command="celery" \
  --args="-A,src.worker.celery_app,worker,--loglevel=info" \
  --set-env-vars="ENVIRONMENT=production" \
  --set-env-vars="DEFAULT_TENANT_SLUG=ourfamroots-system" \
  --set-env-vars="DATABASE_URL=postgresql+asyncpg://$DB_USER:$(gcloud secrets versions access latest --secret=DB_PASSWORD)@/$DB_NAME?host=/cloudsql/$CLOUD_SQL_CONN" \
  --set-env-vars="REDIS_URL=redis://$REDIS_HOST:6379/0" \
  --set-env-vars="S3_BUCKET=$BUCKET,S3_REGION=$REGION" \
  --set-env-vars="S3_ENDPOINT_URL=$S3_ENDPOINT,S3_PUBLIC_URL=$S3_PUBLIC_URL" \
  --set-env-vars="SMTP_HOST=smtp.gmail.com,SMTP_PORT=587" \
  --set-secrets="JWT_SECRET_KEY=JWT_SECRET_KEY:latest" \
  --set-secrets="AWS_ACCESS_KEY_ID=GCS_HMAC_KEY:latest" \
  --set-secrets="AWS_SECRET_ACCESS_KEY=GCS_HMAC_SECRET:latest" \
  --set-secrets="SMTP_USER=SMTP_USER:latest,SMTP_PASSWORD=SMTP_PASSWORD:latest" \
  --min-instances=1 \
  --max-instances=2 \
  --memory=512Mi
```

**Deploy the frontend:**

```bash
export API_URL=$(gcloud run services describe ourfamroots-api \
  --region=$REGION --format="value(status.url)")

gcloud run deploy ourfamroots-frontend \
  --image=$IMAGE_BASE/frontend:$TAG \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="VITE_API_BASE_URL=$API_URL/api/v1" \
  --min-instances=0 \
  --max-instances=2 \
  --memory=256Mi
```

### 6. Run migrations and seed data

Use **Cloud Run Jobs** to run one-off tasks without keeping a service alive:

```bash
export DB_URL="postgresql+asyncpg://$DB_USER:$(gcloud secrets versions access latest --secret=DB_PASSWORD)@/$DB_NAME?host=/cloudsql/$CLOUD_SQL_CONN"

# Create the migration job
gcloud run jobs create ourfamroots-migrate \
  --image=$IMAGE_BASE/api:$TAG \
  --region=$REGION \
  --add-cloudsql-instances=$CLOUD_SQL_CONN \
  --vpc-connector=$VPC_CONNECTOR \
  --command="alembic" \
  --args="upgrade,head" \
  --set-env-vars="DATABASE_URL=$DB_URL"

# Run it and wait
gcloud run jobs execute ourfamroots-migrate --region=$REGION --wait

# Create the seed job
gcloud run jobs create ourfamroots-seed \
  --image=$IMAGE_BASE/api:$TAG \
  --region=$REGION \
  --add-cloudsql-instances=$CLOUD_SQL_CONN \
  --vpc-connector=$VPC_CONNECTOR \
  --command="python" \
  --args="scripts/seed_users.py" \
  --set-env-vars="DATABASE_URL=$DB_URL"

# Run it and wait
gcloud run jobs execute ourfamroots-seed --region=$REGION --wait
```

> To re-run migrations after a future code update, just re-execute the job:
> `gcloud run jobs execute ourfamroots-migrate --region=$REGION --wait`

### 7. Access the app

```bash
# Print your live URLs
echo "Frontend: $(gcloud run services describe ourfamroots-frontend \
  --region=$REGION --format='value(status.url)')"
echo "API:      $(gcloud run services describe ourfamroots-api \
  --region=$REGION --format='value(status.url)')"
```

Log in with any [seed account](#system-accounts) or register a new account.

> Cloud Run scales to zero when idle. The first request after a period of inactivity
> takes a few extra seconds for a cold start. Set `--min-instances=1` on the API
> service to eliminate cold starts (uses more trial credit).

### Estimated trial costs

| Service | Config | Est. cost / month |
| --- | --- | --- |
| Cloud Run (API + Frontend + Worker) | Scale-to-zero, low traffic | < $5 |
| Cloud SQL for PostgreSQL | `db-f1-micro`, 10 GB SSD | ~$8 |
| Memorystore for Redis | Basic tier, 1 GB | ~$35 |
| Cloud Storage | First 5 GB/month free | ~$0 |
| Artifact Registry | First 0.5 GB free | < $1 |
| VPC Access Connector | Low throughput | < $1 |
| **Total** | | **~$49 / month** |

The $300 trial credit covers approximately **6 months** at minimal traffic before any
charges apply.

> **Reducing spend:** Patch the Cloud SQL instance to stop when unused:
>
> ```bash
> gcloud sql instances patch $DB_INSTANCE --activation-policy=NEVER
> # Restart it when needed:
> gcloud sql instances patch $DB_INSTANCE --activation-policy=ALWAYS
> ```
>
> Memorystore cannot be paused — delete and recreate it to save ~$35/month during
> extended idle periods.

### Tearing down

Remove all GCP resources created by this guide to stop all billing:

```bash
# Cloud Run services and jobs
gcloud run services delete ourfamroots-api ourfamroots-frontend ourfamroots-worker \
  --region=$REGION --quiet
gcloud run jobs delete ourfamroots-migrate ourfamroots-seed \
  --region=$REGION --quiet

# Cloud SQL instance (WARNING: destroys all data)
gcloud sql instances delete $DB_INSTANCE --quiet

# Memorystore
gcloud redis instances delete $REDIS_INSTANCE --region=$REGION --quiet

# VPC connector
gcloud compute networks vpc-access connectors delete $VPC_CONNECTOR \
  --region=$REGION --quiet

# Cloud Storage bucket and contents
gcloud storage rm -r gs://$BUCKET

# Artifact Registry
gcloud artifacts repositories delete $AR_REPO --location=$REGION --quiet

# Secret Manager secrets
for SECRET in JWT_SECRET_KEY DB_PASSWORD GCS_HMAC_KEY GCS_HMAC_SECRET \
              SMTP_USER SMTP_PASSWORD; do
  gcloud secrets delete $SECRET --quiet
done
```

---

## Port Reference

| Port | Service | Notes |
| --- | --- | --- |
| 7000 | PostgreSQL | Primary database |
| 7001 | Redis | Cache and Celery broker |
| 7002 | MinIO S3 API | Also used as `S3_PUBLIC_URL` for presigned download links |
| 7003 | MinIO Console | Web UI — `minioadmin` / `minioadmin` |
| 7004 | Backend API | REST API + `/docs` (Swagger) |
| 7005 | Flower | Celery task monitor |
| 7006 | Frontend | Vite dev server |
| 7007 | Prometheus | Monitoring stack only |
| 7008 | Alertmanager | Monitoring stack only |
| 7009 | Grafana | Monitoring stack only |
| 7010 | Loki | Monitoring stack only |
| 7011 | Postgres Exporter | Monitoring stack only |
| 7012 | Redis Exporter | Monitoring stack only |

---

## Troubleshooting

### Photos / avatars return 500 through `/s3/` on the docker-compose VM deployment

**Symptom:** person avatars and gallery photos show as broken images (name, badges, and
relationships still load fine, since those come straight from the API/DB). In the browser
DevTools Network tab, the failing requests are `GET https://<domain>/s3/...jpg?X-Amz-...`
returning `500 Internal Server Error` with an HTML body (not MinIO's XML error format).

This has shown up from two independent causes — check both:

1. **`docker compose` was run without `--env-file .env.prod`.**
   `docker-compose.prod.yml` only works with production secrets when every invocation
   includes `--env-file .env.prod` (Compose does not auto-load a file named anything other
   than `.env`). Without it, `S3_PUBLIC_URL`, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`,
   `JWT_SECRET_KEY`, etc. all silently fall back to blank, which breaks presigned URL
   generation. Symptom in logs: a wall of
   `WARN[0000] The "X" variable is not set. Defaulting to a blank string.` on every
   `docker compose` command. Fix: always pass `--env-file .env.prod`, and confirm with
   `docker compose -f docker-compose.prod.yml --env-file .env.prod exec api env | grep S3_PUBLIC_URL`.

2. **nginx logs `using uninitialized "minio_upstream" variable` / `invalid URL prefix in ""`.**
   In `infra/nginx/proxy.conf`, the `location /s3/` block sets `$minio_upstream` via `set` and
   proxies to it with `proxy_pass $minio_upstream`. `set`, `rewrite`, and `if` all belong to
   nginx's rewrite module and run in the order they're written — a `rewrite ... break;` placed
   **before** a `set` statement stops that `set` from ever running, leaving the variable
   uninitialized and `proxy_pass` pointing at an empty string. The `set` (and `resolver`) lines
   must come before the `rewrite` line in that block. Verify with:
   `docker compose -f docker-compose.prod.yml --env-file .env.prod exec proxy nginx -T | grep -A5 "location /s3/ {"`.

   After editing `infra/nginx/proxy.conf`, `nginx -s reload` is **not always enough** to pick up
   the change — Docker's single-file bind mount can keep pointing at the pre-edit file/inode
   (e.g. after `git pull` atomically replaces the file on disk), so the running nginx config
   silently stays stale even though `nginx -t`/`-s reload` report success. Force the container to
   re-establish the mount instead:

   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate proxy
   ```

   Confirm the fix actually took effect before retesting in the browser:

   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod exec proxy stat -c '%y %n' /etc/nginx/conf.d/default.conf
   docker compose -f docker-compose.prod.yml --env-file .env.prod exec proxy nginx -T | grep -A5 "location /s3/ {"
   ```

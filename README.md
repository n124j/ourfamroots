# OurFamRoots

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
    - [Prerequisites](#prerequisites-1)
    - [1. Configure secrets](#1-configure-secrets)
    - [2. Build and push images](#2-build-and-push-images)
    - [3. Deploy with Helm](#3-deploy-with-helm)
    - [4. Verify the deployment](#4-verify-the-deployment)
    - [Rolling back](#rolling-back)
    - [CI/CD pipeline](#cicd-pipeline)
  - [Port Reference](#port-reference)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
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

**`DEFAULT_TENANT_SLUG`** — OurFamRoots is single-tenant. All registered users join one
shared tenant identified by this slug. Changing it after data is seeded requires a data migration.

**`S3_PUBLIC_URL`** — Presigned MinIO download URLs are rewritten to this host before being
returned to the browser. The internal `minio:9000` hostname is unreachable outside Docker,
so this must point to the externally reachable MinIO API port (`http://localhost:7002` locally).

**`SUPER_ADMIN_EMAIL`** — (Optional) The email address of the Super Administrator.
This user automatically receives the `SUPER_ADMIN` role on login and gets:

- **Full visibility** — can see all trees and all users across the platform
- **Maintenance mode** — can toggle the site to "Under Construction" with a custom message (Admin Dashboard → Site Settings)
- **Broadcast email** — can compose and send emails to all users or selected recipients (Admin Dashboard → Broadcast), with full history tracking
- Users can unsubscribe from broadcast emails in Settings → Notifications

### 2. Start core services

```bash
docker compose up -d
```

This starts:

| Service | Description | Port |
|---------|-------------|------|
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
|-------|----------|------|
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
|---------|-----|-------|
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
ancestors climbing upward). Use the toolbar to switch between:

| Button | Mode | Description |
|--------|------|-------------|
| ↕ | Vertical | Top-to-bottom generation layout |
| ↔ | Horizontal | Left-to-right generation layout |
| ↑ | Ancestor | Focus at bottom, ancestors above (default) |
| ↓ | Descendant | Focus at top, descendants below |
| ◑ | Fan chart | 180° semicircular fan |
| ◎ | Ancestry fan chart | Full SVG fan chart — up to 8 rings with hover tooltips |
| ⊢ | Pedigree | Horizontal binary ancestor tree |

Hovering over any wedge in the fan chart shows a tooltip with the person's full name,
relationship label (e.g. "3× Great-grandparent"), and birth–death years.

#### View Styles & Extensions

Two dropdown menus at the end of the toolbar provide alternate rendering:

**🎨 View Styles** (built-in):

| Style | Description |
|-------|-------------|
| Default | Standard modern card view |
| Heritage | Vintage parchment cards with serif text, sepia photo filter, orthogonal (right-angle) connecting lines |

**🧩 Extensions** (plug-in views):

| Extension | Description |
|-----------|-------------|
| Timeline | Horizontal year-axis view — each person is a coloured bar from birth to death |
| Grid Cards | Sortable card grid (example extension) |

View Styles are independent of the colour theme — you can use Heritage with Dark theme, for example.

#### Extension Plugin System

View extensions live in `frontend/src/extensions/views/`. Each extension is a folder
with an `index.ts` that exports a `ViewPlugin` object. The registry auto-discovers all
extensions via `import.meta.glob` at build time.

```
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

#### Import / Export (.frt)

OurFamRoots uses a native `.frt` backup format (JSON-based) for tree import and export.
The format preserves all person data including:

| Field | Description |
|-------|-------------|
| `display_given_name` / `display_surname` | Name fields |
| `sex` | MALE, FEMALE, OTHER, UNKNOWN |
| `is_living` / `is_deceased` | Living status |
| `photo_url` | Profile photo URL |
| `birth_date` / `death_date` | Full ISO dates (YYYY-MM-DD) |
| `birth_year` / `death_year` | Year-only fallback when full date is unknown |
| `facebook_handle` / `x_handle` / `linkedin_handle` | Social profile handles |

Family groups also preserve `custom_label` (user-defined union labels) and `union_type`.

**Export:** From the tree toolbar, click **Export as .frt** to download the full tree backup.

**Import:** From the dashboard, click **Import tree** and upload a `.frt` file. All persons
are re-created with new UUIDs and the importing user becomes the tree owner.

#### Admin Dashboard

Accessible to ADMIN-role accounts:

- Manually verify / unverify user accounts
- Deactivate / reactivate users (email notifications sent on each action)
- All admin actions appear in the Activity feed

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
|--------|-------------|
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

### Prerequisites

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
|--------|-------------|
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
|--------|---------|----------|
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

## Port Reference

| Port | Service | Notes |
|------|---------|-------|
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

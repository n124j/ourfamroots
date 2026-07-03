# OurFamRoots — Docker Compose Deploy Runbook (Production VM)

Scope: the single-VM Docker Compose production deployment (`docker-compose.prod.yml`,
GCP trial VM). This is a different deployment target from the Kubernetes-oriented
`docs/runbook-disaster-recovery.md` — that doc assumes a cluster (`kubectl`/`helm`);
this one assumes SSH access to the VM and `docker compose`.

---

## Standard deploy steps (any code/config change)

Run from `~/ourfamroots` on the VM.

### 1. Pull the latest code

```bash
git pull
```

### 2. Always pass `--env-file .env.prod` explicitly

Compose only auto-loads a file literally named `.env` — never `.env.prod`. Omitting
this flag silently loads **zero** secrets (every variable defaults to a blank string)
instead of erroring.

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml <command>
```

### 3. Scope the command to what actually changed

Don't run a bare `up -d <service>` for a single-service change without thinking
about its dependency graph — Compose will pull in and potentially recreate every
upstream dependency (`proxy` → `api` → `redis`/`db`/`migrate`), which can cascade
into unrelated services if the environment isn't fully correct (see Incident #1
below).

If you only changed one service's config, recreate **only** that service:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  up -d --force-recreate --no-deps <service>
```

Use `--force-recreate` any time you changed a **bind-mounted file** (nginx configs,
etc.) — see Incident #2 below for why a plain `up -d` or `nginx -s reload` is not
sufficient in that case.

### 4. Verify the change actually landed inside the container

Don't just trust that the command exited successfully.

```bash
docker compose -f docker-compose.prod.yml exec <service> \
  grep -c "<something unique to your change>" <path-in-container>
```

### 5. Check overall health

```bash
docker compose -f docker-compose.prod.yml ps
```

Everything should show `healthy` or `Running`, with no unexpected recreations of
services you didn't intend to touch.

### 6. Functionally test the change

A clean reload/recreate only proves the config loaded, not that the logic is
correct. Hit the actual endpoint/page before calling it done, e.g.:

```bash
curl -s -A "facebookexternalhit/1.1" https://ourfamroots.com/<path> | grep -i "<expected content>"
```

---

## Incident #1 — missing `--env-file .env.prod` cascades into a Redis crash loop

### Symptoms

- `docker compose ... up -d <service>` output shows unrelated services being
  `Recreated`
- `redis-1` stuck `Restarting (1)`
- `worker-1` unhealthy, logs show `redis.exceptions.ConnectionError: ... Broken pipe`
- Redis logs show:
  ```
  *** FATAL CONFIG FILE ERROR ***
  >>> 'requirepass "--appendonly" "yes"'
  wrong number of arguments
  ```

### Root cause

`--env-file .env.prod` was omitted. Compose defaulted to loading no environment at
all. Redis's startup command (`redis-server --requirepass ${REDIS_PASSWORD}
--appendonly yes`) collapsed into `--requirepass  --appendonly yes` with the
password blank — Redis's arg parser then read `--appendonly` as the (missing)
password value and `yes` as a stray token, hence "wrong number of arguments."

This only surfaced because the command's dependency graph forced Redis to be
recreated for the first time in days; it had been running fine beforehand on a
correct environment from a prior deploy.

### Fix

Re-run the same command **with** `--env-file .env.prod`, applied to the whole
stack so dependent services (`api`, `worker`) that also got touched are
reconciled with matching, correct secrets:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps   # confirm redis/api/worker healthy
```

---

## Incident #2 — bind-mounted config file changes silently not applied

### Symptoms

- `grep` on the host confirms the new config content is present in the repo file
- `docker compose exec <service> nginx -s reload` (or equivalent) succeeds with
  no error
- Behavior is still the OLD behavior — no error, just stale content, as if the
  change was never made
- `docker compose exec <service> grep -c "<new content>" <path-in-container>`
  returns `0`, even though the same grep on the host file returns a match

### Root cause

Docker binds a single-file bind mount to the file's **inode**, not its path.
`git pull` (and most editors/tools) replace a file by writing a new temp file and
renaming it over the original — this creates a **new inode**. A container that
was started before that pull keeps its bind mount attached to the **old, now
orphaned inode**, so it keeps serving whatever content the file had at container
creation time (or the last recreate), completely disconnected from what the
path now points to on the host — indefinitely, across any number of `git pull`s,
until the container itself is recreated.

Confirm this is what's happening:

```bash
docker inspect <container> --format '{{json .Mounts}}' | python3 -m json.tool
docker compose -f docker-compose.prod.yml exec <service> \
  grep -c "<new content>" <path-in-container>   # 0 = confirms stale inode
```

### Fix

Only a full container recreate re-attaches the bind mount to the current file.
Reload/restart is **not** enough.

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  up -d --force-recreate --no-deps <service>

# Re-verify:
docker compose -f docker-compose.prod.yml exec <service> \
  grep -c "<new content>" <path-in-container>   # should now be > 0
```

`--no-deps` keeps the blast radius to just that one container — important, given
Incident #1 above.

---

## Quick reference: symptom → cause → fix

| Symptom | Likely cause | Fix |
|---|---|---|
| Every env var logged as "not set, defaulting to blank" | Missing `--env-file .env.prod` | Add the flag to every compose command |
| A service crash-loops right after an `up -d` targeting a *different* service | Dependency cascade picked up bad/blank env | Re-run with correct `--env-file`; check `docker compose ps` for anything unexpectedly `Recreated` |
| Config change confirmed on disk, reload succeeds, behavior unchanged | Bind-mounted file replaced via new inode; container still on the old one | `up -d --force-recreate --no-deps <service>` |
| Need to confirm a fix is *actually* live, not just "should be" | — | `exec ... grep` inside the container, then a real `curl` test — never trust command exit codes alone |

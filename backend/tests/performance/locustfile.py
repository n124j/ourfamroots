"""
Locust performance test plan for OurFamRoots API.

Run:
  locust -f tests/performance/locustfile.py --headless \
         -u 200 -r 20 --run-time 120s \
         --host http://localhost:8000

Targets:
  Name search:         200 RPS, p99 < 100ms
  Ancestor BFS 10gen:  50  RPS, p99 < 200ms
  Upload URL request:  100 RPS, p99 < 50ms
  Auth token refresh:  500 RPS, p99 < 30ms
"""
from __future__ import annotations

import json
import os
import random
import uuid

from locust import HttpUser, between, task

# ── Seed data ──────────────────────────────────────────────────────────────────

TREE_IDS   = [str(uuid.uuid4()) for _ in range(5)]
PERSON_IDS = [str(uuid.uuid4()) for _ in range(50)]
SURNAMES   = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Davis", "Miller"]

API_EMAIL    = os.environ.get("PERF_EMAIL",    "perf@ourfamroots.test")
API_PASSWORD = os.environ.get("PERF_PASSWORD", "Str0ng!Pass#2024")


class OurFamRootsUser(HttpUser):
    """Simulates a typical user session: search, view, occasionally upload."""

    wait_time = between(0.5, 2.0)
    token: str = ""

    def on_start(self):
        """Obtain JWT on session start."""
        r = self.client.post("/api/v1/auth/login", json={
            "email": API_EMAIL,
            "password": API_PASSWORD,
        })
        if r.status_code == 200:
            self.token = r.json().get("access_token", "")

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    # ── Tasks with weights ─────────────────────────────────────────────────────

    @task(10)
    def search_by_name(self):
        q = random.choice(SURNAMES)
        self.client.get(
            f"/api/v1/search?q={q}",
            headers=self._auth(),
            name="GET /search [name]",
        )

    @task(10)
    def search_within_tree(self):
        tree = random.choice(TREE_IDS)
        q    = random.choice(SURNAMES)
        self.client.get(
            f"/api/v1/trees/{tree}/search?q={q}",
            headers=self._auth(),
            name="GET /trees/{id}/search",
        )

    @task(5)
    def get_ancestors(self):
        tree   = random.choice(TREE_IDS)
        person = random.choice(PERSON_IDS)
        self.client.get(
            f"/api/v1/trees/{tree}/persons/{person}/ancestors?max_depth=10",
            headers=self._auth(),
            name="GET ancestors (10gen)",
        )

    @task(3)
    def get_descendants(self):
        tree   = random.choice(TREE_IDS)
        person = random.choice(PERSON_IDS)
        self.client.get(
            f"/api/v1/trees/{tree}/persons/{person}/descendants?max_depth=5",
            headers=self._auth(),
            name="GET descendants (5gen)",
        )

    @task(2)
    def get_relationship(self):
        tree = random.choice(TREE_IDS)
        p1, p2 = random.sample(PERSON_IDS, 2)
        self.client.get(
            f"/api/v1/trees/{tree}/persons/{p1}/relationship?target={p2}",
            headers=self._auth(),
            name="GET relationship path",
        )

    @task(3)
    def request_upload_url(self):
        tree = random.choice(TREE_IDS)
        self.client.post(
            "/api/v1/media/upload-url",
            json={
                "tree_id": tree,
                "original_filename": "photo.jpg",
                "content_type": "image/jpeg",
                "file_size_bytes": random.randint(100_000, 5_000_000),
            },
            headers=self._auth(),
            name="POST /media/upload-url",
        )

    @task(1)
    def refresh_token(self):
        """Simulates silent token refresh (httpOnly cookie flow)."""
        self.client.post(
            "/api/v1/auth/refresh",
            name="POST /auth/refresh",
        )


class HeavySearchUser(HttpUser):
    """Stress test: only name search, high concurrency."""

    wait_time = between(0.1, 0.5)
    token: str = ""

    def on_start(self):
        r = self.client.post("/api/v1/auth/login", json={
            "email": API_EMAIL,
            "password": API_PASSWORD,
        })
        if r.status_code == 200:
            self.token = r.json().get("access_token", "")

    @task
    def search(self):
        q = random.choice(SURNAMES)
        self.client.get(
            f"/api/v1/search?q={q}",
            headers={"Authorization": f"Bearer {self.token}"},
            name="GET /search [stress]",
        )

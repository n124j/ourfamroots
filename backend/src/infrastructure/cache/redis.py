"""Redis client initialisation and RedisRefreshTokenRepository.

The refresh-token store is a simple Redis SET with a TTL:

    Key:   ourfamroots:refresh:<jti>
    Value: <user_id>
    TTL:   refresh_token_expire_days * 86400

A key-scan on `ourfamroots:refresh:user:<user_id>:*` handles "logout all
sessions". We use a secondary index:

    Key:   ourfamroots:refresh:user:<user_id>:<jti>
    Value: 1
    TTL:   same as primary

Revoke all → SCAN + DEL the user-index keys, then DEL the primary keys.
"""

from __future__ import annotations

import json
import uuid

import redis.asyncio as aioredis

from src.domain.interfaces.repositories import AbstractRefreshTokenRepository

# Module-level singleton
_redis: aioredis.Redis | None = None

PRIMARY_PREFIX = "ourfamroots:refresh:"
USER_INDEX_PREFIX = "ourfamroots:refresh:user:"
PENDING_LOGIN_PREFIX = "ourfamroots:pending_login:"


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    return _redis


async def init_redis(redis_url: str) -> None:
    global _redis
    _redis = aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    # Verify connectivity
    await _redis.ping()


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


class RedisRefreshTokenRepository(AbstractRefreshTokenRepository):
    """Stores refresh token JTIs in Redis with automatic expiry."""

    def __init__(self, client: aioredis.Redis | None = None) -> None:
        self._redis = client or get_redis()

    def _primary_key(self, jti: str) -> str:
        return f"{PRIMARY_PREFIX}{jti}"

    def _user_index_key(self, user_id: uuid.UUID, jti: str) -> str:
        return f"{USER_INDEX_PREFIX}{user_id}:{jti}"

    async def store(
        self,
        jti: str,
        user_id: uuid.UUID,
        expires_in_seconds: int,
    ) -> None:
        pipe = self._redis.pipeline()
        pipe.setex(self._primary_key(jti), expires_in_seconds, str(user_id))
        pipe.setex(self._user_index_key(user_id, jti), expires_in_seconds, "1")
        await pipe.execute()

    async def exists(self, jti: str) -> bool:
        return bool(await self._redis.exists(self._primary_key(jti)))

    async def revoke(self, jti: str) -> None:
        # Read user_id from primary key to delete user-index entry too
        user_id_str = await self._redis.get(self._primary_key(jti))
        pipe = self._redis.pipeline()
        pipe.delete(self._primary_key(jti))
        if user_id_str:
            pipe.delete(self._user_index_key(uuid.UUID(user_id_str), jti))
        await pipe.execute()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        pattern = f"{USER_INDEX_PREFIX}{user_id}:*"
        cursor = 0
        jtis: list[str] = []

        while True:
            cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
            for key in keys:
                # key = ourfamroots:refresh:user:<uid>:<jti>
                jti = key.split(":")[-1]
                jtis.append(jti)
            if cursor == 0:
                break

        if not jtis:
            return

        pipe = self._redis.pipeline()
        for jti in jtis:
            pipe.delete(self._primary_key(jti))
            pipe.delete(self._user_index_key(user_id, jti))
        await pipe.execute()

    async def has_active_sessions(self, user_id: uuid.UUID) -> bool:
        pattern = f"{USER_INDEX_PREFIX}{user_id}:*"
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
            if keys:
                return True
            if cursor == 0:
                break
        return False

    def _pending_login_key(self, token: str) -> str:
        return f"{PENDING_LOGIN_PREFIX}{token}"

    async def store_pending_login(
        self, token: str, user_id: uuid.UUID, ip_address: str | None, expires_in_seconds: int,
    ) -> None:
        data = json.dumps({"user_id": str(user_id), "ip_address": ip_address})
        await self._redis.setex(self._pending_login_key(token), expires_in_seconds, data)

    async def get_pending_login(self, token: str) -> dict | None:
        raw = await self._redis.get(self._pending_login_key(token))
        if raw is None:
            return None
        return json.loads(raw)

    async def delete_pending_login(self, token: str) -> None:
        await self._redis.delete(self._pending_login_key(token))

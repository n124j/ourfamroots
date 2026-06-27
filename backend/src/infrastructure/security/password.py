"""Password hashing and verification via passlib + bcrypt."""

from __future__ import annotations

from passlib.context import CryptContext

# bcrypt with cost factor 12 (≈250 ms on modern hardware — safe against brute-force)
_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


class PasswordHasher:
    """Thin wrapper around passlib so the rest of the app never imports passlib directly."""

    @staticmethod
    def hash(plain_password: str) -> str:
        """Return a bcrypt hash string."""
        return _ctx.hash(plain_password)

    @staticmethod
    def verify(plain_password: str, hashed_password: str) -> bool:
        """
        Return True if plain_password matches hashed_password.
        Never raises — returns False on any mismatch or malformed hash.
        """
        try:
            return _ctx.verify(plain_password, hashed_password)
        except Exception:
            return False

    @staticmethod
    def needs_rehash(hashed_password: str) -> bool:
        """
        Return True if the hash was created with an outdated bcrypt config
        (e.g. cost factor was bumped) and should be re-hashed on next login.
        """
        return _ctx.needs_update(hashed_password)

"""
Seed the three pre-defined system users.

Run from the backend/ directory:
    python scripts/seed_users.py

Requires the DATABASE_URL env var or a .env file.
Creates the users if they don't already exist, updates app_role if they do.
"""
from __future__ import annotations

import asyncio
import os
import sys

# Make sure 'src' is importable when run from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import get_settings
from src.infrastructure.database.models.tenant import TenantModel
from src.infrastructure.database.models.user import UserModel
from src.infrastructure.security.password import PasswordHasher

# ── Seed data ──────────────────────────────────────────────────────────────────

SEED_USERS = [
    {
        "email": "admin@ourfamroots.app",
        "password": "Admin@FR2024!",
        "given_name": "System",
        "family_name": "Administrator",
        "app_role": "ADMIN",
    },
    {
        "email": "user@ourfamroots.app",
        "password": "User@FR2024!",
        "given_name": "Standard",
        "family_name": "User",
        "app_role": "STANDARD",
    },
    {
        "email": "auditor@ourfamroots.app",
        "password": "Auditor@FR2024!",
        "given_name": "System",
        "family_name": "Auditor",
        "app_role": "AUDITOR",
    },
]

SEED_TENANT_SLUG = "ourfamroots-system"


async def seed() -> None:
    settings = get_settings()
    hasher = PasswordHasher()

    engine = create_async_engine(settings.database_url_str, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Ensure tenant exists
        result = await session.execute(
            select(TenantModel).where(TenantModel.slug == SEED_TENANT_SLUG)
        )
        tenant = result.scalars().first()
        if tenant is None:
            tenant = TenantModel(
                name="OurFamRoots System",
                slug=SEED_TENANT_SLUG,
                is_active=True,
            )
            session.add(tenant)
            await session.flush()
            print(f"  Created tenant: {SEED_TENANT_SLUG}  id={tenant.id}")
        else:
            print(f"  Using existing tenant: {SEED_TENANT_SLUG}  id={tenant.id}")

        for spec in SEED_USERS:
            result = await session.execute(
                select(UserModel).where(
                    UserModel.email == spec["email"],
                    UserModel.tenant_id == tenant.id,
                )
            )
            user = result.scalars().first()

            if user is None:
                user = UserModel(
                    tenant_id=tenant.id,
                    email=spec["email"],
                    password_hash=hasher.hash(spec["password"]),
                    given_name=spec["given_name"],
                    family_name=spec["family_name"],
                    app_role=spec["app_role"],
                    email_verified=True,
                    is_active=True,
                )
                session.add(user)
                print(f"  Created [{spec['app_role']:8}] {spec['email']}")
            else:
                user.password_hash = hasher.hash(spec["password"])
                user.app_role = spec["app_role"]
                user.email_verified = True
                user.is_active = True
                print(f"  Updated [{spec['app_role']:8}] {spec['email']}")

        await session.commit()

    await engine.dispose()
    print("\nDone.")
    print("\nCredentials:")
    print(f"  {'Role':<10}  {'Email':<32}  Password")
    print(f"  {'-'*10}  {'-'*32}  {'-'*20}")
    for s in SEED_USERS:
        print(f"  {s['app_role']:<10}  {s['email']:<32}  {s['password']}")


if __name__ == "__main__":
    asyncio.run(seed())

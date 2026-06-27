"""
factory-boy + faker test data factories.
All factories are framework-agnostic — they produce domain entities or
ORM model instances usable by both unit and integration tests.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import factory
from factory import fuzzy
from faker import Faker

fake = Faker()


# ── Person factories ───────────────────────────────────────────────────────────

class PersonFactory(factory.Factory):
    """Produces a dict suitable for POST /persons or direct ORM construction."""

    class Meta:
        model = dict

    id           = factory.LazyFunction(uuid.uuid4)
    tree_id      = factory.LazyFunction(uuid.uuid4)
    tenant_id    = factory.LazyFunction(uuid.uuid4)
    given_name   = factory.LazyAttribute(lambda _: fake.first_name())
    surname      = factory.LazyAttribute(lambda _: fake.last_name())
    maiden_name  = None
    sex          = fuzzy.FuzzyChoice(["M", "F", "U"])
    birth_year   = fuzzy.FuzzyInteger(1800, 2000)
    death_year   = None
    birth_place  = factory.LazyAttribute(lambda _: fake.city())
    is_living    = False
    notes        = ""
    is_deleted   = False
    created_at   = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at   = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class LivingPersonFactory(PersonFactory):
    birth_year = fuzzy.FuzzyInteger(1940, 2005)
    is_living  = True
    death_year = None


class HistoricalPersonFactory(PersonFactory):
    birth_year = fuzzy.FuzzyInteger(1700, 1900)
    death_year = factory.LazyAttribute(lambda o: o.birth_year + fuzzy.FuzzyInteger(20, 85).fuzz())
    is_living  = False


# ── Media factories ────────────────────────────────────────────────────────────

class MediaItemFactory(factory.Factory):
    class Meta:
        model = dict

    id                = factory.LazyFunction(uuid.uuid4)
    tree_id           = factory.LazyFunction(uuid.uuid4)
    tenant_id         = factory.LazyFunction(uuid.uuid4)
    uploaded_by_id    = factory.LazyFunction(uuid.uuid4)
    person_id         = factory.LazyFunction(uuid.uuid4)
    original_filename = factory.LazyAttribute(lambda _: f"{fake.word()}.jpg")
    content_type      = "image/jpeg"
    file_size_bytes   = fuzzy.FuzzyInteger(10_000, 5_000_000)
    category          = "PHOTO"
    status            = "PENDING"
    original_key      = factory.LazyAttribute(
        lambda o: f"{o.tenant_id}/{o.tree_id}/persons/{o.person_id}/{o.id}/original.jpg"
    )
    tags              = factory.LazyFunction(list)
    created_at        = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at        = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    is_deleted        = False


# ── Auth factories ─────────────────────────────────────────────────────────────

class RegisterPayloadFactory(factory.Factory):
    class Meta:
        model = dict

    email      = factory.LazyAttribute(lambda _: fake.unique.email())
    password   = "Str0ng!Pass#2024"
    given_name = factory.LazyAttribute(lambda _: fake.first_name())
    surname    = factory.LazyAttribute(lambda _: fake.last_name())


class LoginPayloadFactory(factory.Factory):
    class Meta:
        model = dict

    email    = factory.LazyAttribute(lambda _: fake.unique.email())
    password = "Str0ng!Pass#2024"


# ── Tree factories ─────────────────────────────────────────────────────────────

class CreateTreePayloadFactory(factory.Factory):
    class Meta:
        model = dict

    name        = factory.LazyAttribute(lambda _: f"The {fake.last_name()} Family")
    description = factory.LazyAttribute(lambda _: fake.sentence())


# ── Search query factories ─────────────────────────────────────────────────────

class NameSearchQueryFactory(factory.Factory):
    class Meta:
        from src.domain.search.entities import NameSearchQuery
        model = NameSearchQuery

    raw        = factory.LazyAttribute(lambda _: fake.last_name())
    tenant_id  = factory.LazyFunction(uuid.uuid4)
    tree_id    = factory.LazyFunction(uuid.uuid4)
    limit      = 20
    offset     = 0


# ── Collaboration factories ────────────────────────────────────────────────────

class InvitePayloadFactory(factory.Factory):
    class Meta:
        model = dict

    email = factory.LazyAttribute(lambda _: fake.unique.email())
    role  = "EDITOR"

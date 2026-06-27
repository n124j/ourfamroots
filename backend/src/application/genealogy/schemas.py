"""Pydantic schemas for genealogy API request/response payloads."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from src.domain.genealogy.entities import (
    ParentageType,
    RelationshipKind,
    Sex,
    UnionType,
)


# ── Person schemas ────────────────────────────────────────────────

class CreatePersonRequest(BaseModel):
    given_name: str = Field(default="", max_length=200)
    surname: str = Field(default="", max_length=200)
    sex: Sex = Sex.UNKNOWN
    birth_date: Optional[date] = None
    death_date: Optional[date] = None
    birth_year: Optional[int] = Field(default=None, ge=1, le=9999)
    death_year: Optional[int] = Field(default=None, ge=1, le=9999)
    is_living: bool = True
    is_deceased: bool = False
    born_city: Optional[str] = Field(default=None, max_length=200)
    born_country: Optional[str] = Field(default=None, max_length=100)
    died_city: Optional[str] = Field(default=None, max_length=200)
    died_country: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=250)


class UpdatePersonRequest(BaseModel):
    given_name: str = Field(default="", max_length=200)
    surname: str = Field(default="", max_length=200)
    sex: Sex = Sex.UNKNOWN
    birth_date: Optional[date] = None
    death_date: Optional[date] = None
    birth_year: Optional[int] = Field(default=None, ge=1, le=9999)
    death_year: Optional[int] = Field(default=None, ge=1, le=9999)
    is_living: bool = True
    is_deceased: bool = False
    photo_url: Optional[str] = Field(default=None, max_length=2048)
    born_city: Optional[str] = Field(default=None, max_length=200)
    born_country: Optional[str] = Field(default=None, max_length=100)
    died_city: Optional[str] = Field(default=None, max_length=200)
    died_country: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=250)


class PersonResponse(BaseModel):
    id: uuid.UUID
    tree_id: uuid.UUID
    display_given_name: str
    display_surname: str
    sex: str
    is_living: bool
    is_deceased: bool
    photo_url: Optional[str] = None
    birth_date: Optional[date] = None
    death_date: Optional[date] = None
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    born_city: Optional[str] = None
    born_country: Optional[str] = None
    died_city: Optional[str] = None
    died_country: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class PersonDetailResponse(PersonResponse):
    parents: list[uuid.UUID] = []
    children: list[uuid.UUID] = []
    spouses: list[uuid.UUID] = []
    siblings: list[uuid.UUID] = []


# ── Relationship mutation schemas ─────────────────────────────────

class AddParentRequest(BaseModel):
    parent_id: uuid.UUID
    parentage_type: ParentageType = ParentageType.BIOLOGICAL
    union_type: UnionType = UnionType.UNKNOWN


class AddBothParentsRequest(BaseModel):
    father_id: uuid.UUID
    mother_id: uuid.UUID
    parentage_type: ParentageType = ParentageType.BIOLOGICAL
    union_type: UnionType = UnionType.MARRIAGE


class AddChildRequest(BaseModel):
    child_id: uuid.UUID
    other_parent_id: Optional[uuid.UUID] = None
    parentage_type: ParentageType = ParentageType.BIOLOGICAL
    union_type: UnionType = UnionType.UNKNOWN


class AddSpouseRequest(BaseModel):
    spouse_id: uuid.UUID
    union_type: UnionType = UnionType.MARRIAGE


class AddSiblingRequest(BaseModel):
    sibling_id: uuid.UUID
    parentage_type: ParentageType = ParentageType.BIOLOGICAL


# ── Relationship query response schemas ───────────────────────────

class KinshipResponse(BaseModel):
    person1_id: uuid.UUID
    person2_id: uuid.UUID
    relationship: str              # human-readable label
    kind: RelationshipKind
    cousin_degree: Optional[int] = None
    cousin_removed: Optional[int] = None
    common_ancestor_ids: list[uuid.UUID] = []
    path: list[uuid.UUID] = []


class AncestorsByGenerationResponse(BaseModel):
    """persons grouped by generation (1 = parents, 2 = grandparents, …)"""
    generations: dict[int, list[uuid.UUID]]


class LineagePathResponse(BaseModel):
    nodes: list[uuid.UUID]
    edge_labels: list[str]
    length: int


class FamilyGroupResponse(BaseModel):
    id: uuid.UUID
    union_type: str
    parent_ids: list[uuid.UUID]
    child_ids: list[uuid.UUID]

"""Search API endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user, get_search_service
from src.application.search.service import SearchService
from src.domain.search.exceptions import (
    SearchDepthExceededError,
    SearchQueryTooLongError,
    SearchQueryTooShortError,
)

router = APIRouter(tags=["search"])


# ── Response schemas ───────────────────────────────────────────────────────────

class PersonHitSchema(BaseModel):
    person_id: str
    tree_id: str
    given_name: Optional[str]
    surname: Optional[str]
    maiden_name: Optional[str]
    birth_year: Optional[int]
    death_year: Optional[int]
    birth_place: Optional[str]
    is_living: bool
    score: float


class AncestorHitSchema(BaseModel):
    person_id: str
    given_name: Optional[str]
    surname: Optional[str]
    birth_year: Optional[int]
    death_year: Optional[int]
    depth: int
    relationship_label: str
    is_living: bool


class PathStepSchema(BaseModel):
    person_id: str
    name: str
    sex: Optional[str] = None


class RelationshipPathSchema(BaseModel):
    found: bool
    distance: int
    path: list[PathStepSchema]
    relationship_label: Optional[str]
    alternative_label: Optional[str] = None
    edge_labels: list[str] = []


class NameSearchResponse(BaseModel):
    total: int
    hits: list[PersonHitSchema]
    took_ms: int


class GraphSearchResponse(BaseModel):
    total: int
    items: list[AncestorHitSchema]
    took_ms: int


class RelationshipResponse(BaseModel):
    relationship: RelationshipPathSchema
    took_ms: int


# ── Exception handler ──────────────────────────────────────────────────────────

def _handle(exc: Exception) -> None:
    if isinstance(exc, (SearchQueryTooShortError, SearchQueryTooLongError, SearchDepthExceededError)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message)
    raise exc


# ── Global / tenant-scoped name search ────────────────────────────────────────

@router.get(
    "/search",
    response_model=NameSearchResponse,
    summary="Global name search across all trees in the tenant",
)
async def global_search(
    q: str = Query(..., min_length=2, max_length=200, description="Name query"),
    birth_year_min: Optional[int] = Query(default=None, ge=1, le=2100),
    birth_year_max: Optional[int] = Query(default=None, ge=1, le=2100),
    birth_place: Optional[str]    = Query(default=None, max_length=200),
    limit: int   = Query(default=20, ge=1, le=100),
    offset: int  = Query(default=0,  ge=0),
    sort: str    = Query(default="relevance", pattern="^(relevance|name|birth_year|updated_at)$"),
    fuzzy: bool  = Query(default=True),
    current_user = Depends(get_current_user),
    svc: SearchService = Depends(get_search_service),
):
    try:
        results = await svc.search_names(
            raw=q,
            tenant_id=current_user.tenant_id,
            tree_id=None,
            birth_year_min=birth_year_min,
            birth_year_max=birth_year_max,
            birth_place=birth_place,
            limit=limit,
            offset=offset,
            sort=sort,
            fuzzy=fuzzy,
        )
    except Exception as exc:
        _handle(exc)

    return NameSearchResponse(
        total=results.total,
        hits=[_hit_schema(h) for h in results.hits],
        took_ms=results.took_ms,
    )


# ── Per-tree name search ───────────────────────────────────────────────────────

@router.get(
    "/trees/{tree_id}/search",
    response_model=NameSearchResponse,
    summary="Name search within a specific tree",
)
async def tree_search(
    tree_id: Annotated[uuid.UUID, Path()],
    q: str = Query(..., min_length=2, max_length=200),
    birth_year_min: Optional[int] = Query(default=None),
    birth_year_max: Optional[int] = Query(default=None),
    limit: int  = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str   = Query(default="relevance"),
    fuzzy: bool = Query(default=True),
    current_user = Depends(get_current_user),
    svc: SearchService = Depends(get_search_service),
):
    try:
        results = await svc.search_names(
            raw=q,
            tenant_id=current_user.tenant_id,
            tree_id=tree_id,
            birth_year_min=birth_year_min,
            birth_year_max=birth_year_max,
            limit=limit,
            offset=offset,
            sort=sort,
            fuzzy=fuzzy,
        )
    except Exception as exc:
        _handle(exc)

    return NameSearchResponse(
        total=results.total,
        hits=[_hit_schema(h) for h in results.hits],
        took_ms=results.took_ms,
    )


# ── Ancestor search ────────────────────────────────────────────────────────────

@router.get(
    "/trees/{tree_id}/persons/{person_id}/ancestors",
    response_model=GraphSearchResponse,
    summary="All ancestors of a person up to max_depth generations",
)
async def get_ancestors(
    tree_id:   Annotated[uuid.UUID, Path()],
    person_id: Annotated[uuid.UUID, Path()],
    max_depth: int  = Query(default=10, ge=1, le=30),
    current_user    = Depends(get_current_user),
    svc: SearchService = Depends(get_search_service),
):
    try:
        results = await svc.search_ancestors(
            person_id=person_id,
            tree_id=tree_id,
            tenant_id=current_user.tenant_id,
            max_depth=max_depth,
        )
    except Exception as exc:
        _handle(exc)

    return GraphSearchResponse(
        total=results.total,
        items=[_ancestor_schema(a) for a in results.ancestors],
        took_ms=results.took_ms,
    )


# ── Descendant / branch search ─────────────────────────────────────────────────

@router.get(
    "/trees/{tree_id}/persons/{person_id}/descendants",
    response_model=GraphSearchResponse,
    summary="All descendants of a person (family branch)",
)
async def get_descendants(
    tree_id:   Annotated[uuid.UUID, Path()],
    person_id: Annotated[uuid.UUID, Path()],
    max_depth: int = Query(default=10, ge=1, le=30),
    current_user   = Depends(get_current_user),
    svc: SearchService = Depends(get_search_service),
):
    try:
        results = await svc.search_branch(
            root_person_id=person_id,
            tree_id=tree_id,
            tenant_id=current_user.tenant_id,
            max_depth=max_depth,
        )
    except Exception as exc:
        _handle(exc)

    return GraphSearchResponse(
        total=results.total,
        items=[_ancestor_schema(a) for a in results.ancestors],
        took_ms=results.took_ms,
    )


# ── Relatives ─────────────────────────────────────────────────────────────────

@router.get(
    "/trees/{tree_id}/persons/{person_id}/relatives",
    response_model=GraphSearchResponse,
    summary="All relatives within max_hops of a person",
)
async def get_relatives(
    tree_id:   Annotated[uuid.UUID, Path()],
    person_id: Annotated[uuid.UUID, Path()],
    max_hops: int = Query(default=4, ge=1, le=10),
    current_user  = Depends(get_current_user),
    svc: SearchService = Depends(get_search_service),
):
    try:
        results = await svc.search_relatives(
            person_id=person_id,
            tree_id=tree_id,
            tenant_id=current_user.tenant_id,
            max_hops=max_hops,
        )
    except Exception as exc:
        _handle(exc)

    return GraphSearchResponse(
        total=results.total,
        items=[_ancestor_schema(a) for a in results.ancestors],
        took_ms=results.took_ms,
    )


# ── Relationship path ──────────────────────────────────────────────────────────

@router.get(
    "/trees/{tree_id}/persons/{person_id}/relationship",
    response_model=RelationshipResponse,
    summary="Find relationship path between two people",
)
async def get_relationship(
    tree_id:   Annotated[uuid.UUID, Path()],
    person_id: Annotated[uuid.UUID, Path()],
    target:    uuid.UUID = Query(..., description="The other person's ID"),
    max_depth: int       = Query(default=15, ge=1, le=30),
    current_user  = Depends(get_current_user),
    svc: SearchService = Depends(get_search_service),
):
    try:
        results = await svc.find_relationship(
            person_id_1=person_id,
            person_id_2=target,
            tree_id=tree_id,
            tenant_id=current_user.tenant_id,
            max_depth=max_depth,
        )
    except Exception as exc:
        _handle(exc)

    rel = results.relationship
    return RelationshipResponse(
        relationship=RelationshipPathSchema(
            found=rel.found,
            distance=rel.distance,
            path=[PathStepSchema(person_id=s["person_id"], name=s["name"], sex=s.get("sex")) for s in rel.path],
            relationship_label=rel.relationship_label,
            alternative_label=rel.alternative_label,
            edge_labels=rel.edge_labels,
        ),
        took_ms=results.took_ms,
    )


# ── Schema helpers ─────────────────────────────────────────────────────────────

def _hit_schema(h: Any) -> PersonHitSchema:
    return PersonHitSchema(
        person_id=str(h.person_id),
        tree_id=str(h.tree_id),
        given_name=h.given_name,
        surname=h.surname,
        maiden_name=h.maiden_name,
        birth_year=h.birth_year,
        death_year=h.death_year,
        birth_place=h.birth_place,
        is_living=h.is_living,
        score=h.score,
    )


def _ancestor_schema(a: Any) -> AncestorHitSchema:
    return AncestorHitSchema(
        person_id=str(a.person_id),
        given_name=a.given_name,
        surname=a.surname,
        birth_year=a.birth_year,
        death_year=a.death_year,
        depth=a.depth,
        relationship_label=a.relationship_label,
        is_living=a.is_living,
    )

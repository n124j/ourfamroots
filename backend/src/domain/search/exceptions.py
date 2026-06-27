"""Search domain exceptions."""
from __future__ import annotations

import uuid
from src.domain.exceptions import DomainError, ValidationError


class SearchQueryTooShortError(ValidationError):
    def __init__(self, min_length: int = 2) -> None:
        super().__init__(
            message=f"Search query must be at least {min_length} characters.",
            field="q",
        )
        self.code = "SEARCH_QUERY_TOO_SHORT"


class SearchQueryTooLongError(ValidationError):
    def __init__(self, max_length: int = 200) -> None:
        super().__init__(
            message=f"Search query must not exceed {max_length} characters.",
            field="q",
        )
        self.code = "SEARCH_QUERY_TOO_LONG"


class RelationshipPersonNotFoundError(DomainError):
    def __init__(self, person_id: uuid.UUID) -> None:
        super().__init__(
            message=f"Person {person_id} not found in this tree.",
            code="RELATIONSHIP_PERSON_NOT_FOUND",
        )
        self.person_id = person_id


class RelationshipNotFoundError(DomainError):
    def __init__(self, p1: uuid.UUID, p2: uuid.UUID, max_depth: int) -> None:
        super().__init__(
            message=(
                f"No relationship path found between {p1} and {p2} "
                f"within {max_depth} hops."
            ),
            code="RELATIONSHIP_NOT_FOUND",
        )
        self.person_id_1 = p1
        self.person_id_2 = p2


class SearchDepthExceededError(ValidationError):
    def __init__(self, max_allowed: int = 30) -> None:
        super().__init__(
            message=f"max_depth cannot exceed {max_allowed} generations.",
            field="max_depth",
        )
        self.code = "SEARCH_DEPTH_EXCEEDED"

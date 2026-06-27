"""Collaboration-specific domain exceptions."""
from __future__ import annotations

import uuid
from src.domain.exceptions import ConflictError, DomainError, ValidationError
from src.domain.collaboration.entities import Action, TreeRole


class InsufficientPermissionError(DomainError):
    def __init__(self, action: Action, role: TreeRole) -> None:
        super().__init__(
            message=f"Role '{role.value}' cannot perform '{action.value}'.",
            code="INSUFFICIENT_PERMISSION",
        )
        self.action = action
        self.role = role


class InvitationNotFoundError(DomainError):
    def __init__(self, token: str) -> None:
        super().__init__(
            message="Invitation not found or already used.",
            code="INVITATION_NOT_FOUND",
        )
        self.token = token


class InvitationExpiredError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="This invitation has expired. Please ask for a new one.",
            code="INVITATION_EXPIRED",
        )


class InvitationAlreadyUsedError(ConflictError):
    def __init__(self, status: str) -> None:
        super().__init__(
            f"This invitation has already been {status.lower()}."
        )
        self.code = "INVITATION_ALREADY_USED"


class AlreadyMemberError(ConflictError):
    def __init__(self, user_id: uuid.UUID, tree_id: uuid.UUID) -> None:
        super().__init__(
            f"User {user_id} is already a member of tree {tree_id}."
        )
        self.code = "ALREADY_MEMBER"


class CannotRemoveOwnerError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "Cannot remove the tree owner. Transfer ownership first."
        )
        self.code = "CANNOT_REMOVE_OWNER"


class CannotDowngradeOwnerError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "Cannot change the owner's role. Transfer ownership first."
        )
        self.code = "CANNOT_DOWNGRADE_OWNER"


class OAuthProviderError(DomainError):
    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(
            message=f"OAuth error from {provider}: {detail}",
            code="OAUTH_PROVIDER_ERROR",
        )
        self.provider = provider


class OAuthStateMismatchError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="OAuth state parameter mismatch. Please try signing in again.",
            code="OAUTH_STATE_MISMATCH",
        )

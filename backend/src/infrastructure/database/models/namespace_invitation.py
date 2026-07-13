"""ORM model for namespace invitations (transferring a Global-namespace user into a namespace)."""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.collaboration.entities import InvitationStatus
from src.infrastructure.database.base import Base, TimestampMixin


class NamespaceInvitationModel(Base, TimestampMixin):
    """A pending invitation for an existing (Global-namespace) user to join a namespace."""

    __tablename__ = "namespace_invitations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    inviter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    invitee_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    invitee_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(
        SAEnum(InvitationStatus, name="invitation_status_enum", create_type=False),
        nullable=False,
        server_default=InvitationStatus.PENDING.value,
    )
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<NamespaceInvitationModel email={self.invitee_email} status={self.status}>"

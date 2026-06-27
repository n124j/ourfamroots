"""Person ORM models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer,
    String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.genealogy.entities import ParentageType, Sex
from src.infrastructure.database.base import Base, TenantMixin, TimestampMixin


class PersonModel(Base, TenantMixin, TimestampMixin):
    """Maps to the `persons` table."""

    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tree_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_trees.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    sex: Mapped[str] = mapped_column(
        SAEnum(
            "MALE", "FEMALE", "OTHER", "UNKNOWN",
            name="person_sex", create_type=False,
        ),
        nullable=False, server_default=text("'UNKNOWN'"),
    )
    display_given_name: Mapped[str] = mapped_column(String(200), nullable=False, server_default=text("''"))
    display_surname: Mapped[str] = mapped_column(String(200), nullable=False, server_default=text("''"))
    is_living: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_deceased: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Profile photo URL (thumbnail from media system, set after upload)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Life dates — full date takes priority; year-only is the fallback
    birth_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    death_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    death_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Birth / death location
    born_city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    born_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    died_city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    died_country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Free-text notes
    notes: Mapped[str | None] = mapped_column(String(250), nullable=True)

    # Denormalised search vector (populated by DB trigger)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    family_group_memberships: Mapped[list["FamilyGroupMemberModel"]] = relationship(
        "FamilyGroupMemberModel", back_populates="person", lazy="noload",
    )
    gallery_photos: Mapped[list["PersonGalleryPhotoModel"]] = relationship(
        "PersonGalleryPhotoModel", back_populates="person", lazy="noload",
        order_by="PersonGalleryPhotoModel.position",
    )

    def __repr__(self) -> str:
        return f"<PersonModel id={self.id!s} name={self.display_given_name!r} {self.display_surname!r}>"


class PersonGalleryPhotoModel(Base, TenantMixin, TimestampMixin):
    """Up to 3 additional photos per person, each with an optional caption."""

    __tablename__ = "person_gallery_photos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tree_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_trees.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    photo_url: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    person: Mapped["PersonModel"] = relationship(
        "PersonModel", back_populates="gallery_photos", lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<PersonGalleryPhotoModel id={self.id!s} person_id={self.person_id!s}>"


class FamilyGroupModel(Base, TenantMixin, TimestampMixin):
    """Maps to the `family_groups` table."""

    __tablename__ = "family_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tree_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_trees.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    union_type: Mapped[str] = mapped_column(
        SAEnum(
            "MARRIAGE", "PARTNERSHIP", "COHABITATION", "UNKNOWN",
            name="union_type", create_type=False,
        ),
        nullable=False, server_default=text("'UNKNOWN'"),
    )
    # Denormalised for fast parent-pair lookups (V005 schema)
    parent1_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    parent2_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    is_divorced: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    union_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    union_date_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    union_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    union_end_date_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    members: Mapped[list["FamilyGroupMemberModel"]] = relationship(
        "FamilyGroupMemberModel", back_populates="family_group", lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<FamilyGroupModel id={self.id!s}>"


class FamilyGroupMemberModel(Base, TenantMixin, TimestampMixin):
    """Maps to the `family_group_members` table."""

    __tablename__ = "family_group_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    family_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role: Mapped[str] = mapped_column(
        SAEnum("PARENT", "CHILD", name="family_role", create_type=False),
        nullable=False,
    )
    parentage_type: Mapped[str | None] = mapped_column(
        SAEnum(
            "BIOLOGICAL", "ADOPTIVE", "STEP", "FOSTER", "UNKNOWN",
            name="parentage_type", create_type=False,
        ),
        nullable=True,
    )

    tree_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("family_trees.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    person: Mapped["PersonModel"] = relationship(
        "PersonModel", back_populates="family_group_memberships", lazy="noload",
    )
    family_group: Mapped["FamilyGroupModel"] = relationship(
        "FamilyGroupModel", back_populates="members", lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint("family_group_id", "person_id", name="uq_fgm_fg_person"),
    )

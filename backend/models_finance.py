from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db_meta import Base
from backend.enums_finance import EntryKind, LinkType
from backend.models_shared import utc_now, uuid_str


class EntryGroup(Base):
    __tablename__ = "entry_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    entries: Mapped[list[Entry]] = relationship(back_populates="group")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    accounts: Mapped[list[Account]] = relationship(back_populates="owner_user")
    owned_entries: Mapped[list[Entry]] = relationship(
        back_populates="owner_user", foreign_keys="Entry.owner_user_id"
    )


class RuntimeSettings(Base):
    __tablename__ = "runtime_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, default="default"
    )
    current_user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_memory: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    dashboard_currency_code: Mapped[str | None] = mapped_column(
        String(3), nullable=True
    )
    agent_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_max_steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_retry_max_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_retry_initial_wait_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    agent_retry_max_wait_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    agent_retry_backoff_multiplier: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    agent_max_image_size_bytes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    agent_max_images_per_message: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    agent_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    agent_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    markdown_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    snapshots: Mapped[list[AccountSnapshot]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    entries: Mapped[list[Entry]] = relationship(back_populates="account")
    owner_user: Mapped[User | None] = relationship(back_populates="accounts")
    entity: Mapped[Entity | None] = relationship(back_populates="accounts")


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    balance_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    account: Mapped[Account] = relationship(back_populates="snapshots")


class EntryTag(Base):
    __tablename__ = "entry_tags"

    entry_id: Mapped[str] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    entries: Mapped[list[Entry]] = relationship(
        secondary="entry_tags",
        back_populates="tags",
    )


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    as_source_entries: Mapped[list[Entry]] = relationship(
        back_populates="from_entity_ref",
        foreign_keys="Entry.from_entity_id",
    )
    as_target_entries: Mapped[list[Entry]] = relationship(
        back_populates="to_entity_ref",
        foreign_keys="Entry.to_entity_id",
    )
    accounts: Mapped[list[Account]] = relationship(back_populates="entity")


class Taxonomy(Base):
    __tablename__ = "taxonomies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    key: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    applies_to: Mapped[str] = mapped_column(String(50), nullable=False)
    cardinality: Mapped[str] = mapped_column(
        String(20), nullable=False, default="single"
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    terms: Mapped[list[TaxonomyTerm]] = relationship(
        back_populates="taxonomy",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list[TaxonomyAssignment]] = relationship(
        back_populates="taxonomy",
        cascade="all, delete-orphan",
    )


class TaxonomyTerm(Base):
    __tablename__ = "taxonomy_terms"
    __table_args__ = (
        UniqueConstraint(
            "taxonomy_id", "normalized_name", name="uq_taxonomy_terms_name"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    taxonomy_id: Mapped[str] = mapped_column(
        ForeignKey("taxonomies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    parent_term_id: Mapped[str | None] = mapped_column(
        ForeignKey("taxonomy_terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    taxonomy: Mapped[Taxonomy] = relationship(back_populates="terms")
    parent_term: Mapped[TaxonomyTerm | None] = relationship(
        remote_side=lambda: TaxonomyTerm.id,
        back_populates="child_terms",
    )
    child_terms: Mapped[list[TaxonomyTerm]] = relationship(back_populates="parent_term")
    assignments: Mapped[list[TaxonomyAssignment]] = relationship(
        back_populates="term",
        cascade="all, delete-orphan",
    )


class TaxonomyAssignment(Base):
    __tablename__ = "taxonomy_assignments"
    __table_args__ = (
        UniqueConstraint(
            "taxonomy_id",
            "subject_type",
            "subject_id",
            "term_id",
            name="uq_taxonomy_assignments_subject_term",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    taxonomy_id: Mapped[str] = mapped_column(
        ForeignKey("taxonomies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    term_id: Mapped[str] = mapped_column(
        ForeignKey("taxonomy_terms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    taxonomy: Mapped[Taxonomy] = relationship(back_populates="assignments")
    term: Mapped[TaxonomyTerm] = relationship(back_populates="assignments")


class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    group_id: Mapped[str] = mapped_column(
        ForeignKey("entry_groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[EntryKind] = mapped_column(Enum(EntryKind), nullable=False, index=True)
    occurred_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    from_entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    to_entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    from_entity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_entity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    markdown_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    group: Mapped[EntryGroup] = relationship(back_populates="entries")
    account: Mapped[Account | None] = relationship(back_populates="entries")
    from_entity_ref: Mapped[Entity | None] = relationship(
        back_populates="as_source_entries",
        foreign_keys=[from_entity_id],
    )
    to_entity_ref: Mapped[Entity | None] = relationship(
        back_populates="as_target_entries",
        foreign_keys=[to_entity_id],
    )
    owner_user: Mapped[User | None] = relationship(
        back_populates="owned_entries",
        foreign_keys=[owner_user_id],
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary="entry_tags",
        back_populates="entries",
    )
    outgoing_links: Mapped[list[EntryLink]] = relationship(
        back_populates="source_entry",
        foreign_keys="EntryLink.source_entry_id",
        cascade="all, delete-orphan",
    )
    incoming_links: Mapped[list[EntryLink]] = relationship(
        back_populates="target_entry",
        foreign_keys="EntryLink.target_entry_id",
        cascade="all, delete-orphan",
    )


class EntryLink(Base):
    __tablename__ = "entry_links"
    __table_args__ = (
        UniqueConstraint(
            "source_entry_id",
            "target_entry_id",
            "link_type",
            name="uq_entry_links_tuple",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_entry_id: Mapped[str] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_entry_id: Mapped[str] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    link_type: Mapped[LinkType] = mapped_column(
        Enum(LinkType), nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    source_entry: Mapped[Entry] = relationship(
        back_populates="outgoing_links", foreign_keys=[source_entry_id]
    )
    target_entry: Mapped[Entry] = relationship(
        back_populates="incoming_links", foreign_keys=[target_entry_id]
    )

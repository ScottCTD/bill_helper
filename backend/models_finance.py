# CALLING SPEC:
# - Purpose: provide the `models_finance` module.
# - Inputs: callers that import `backend/models_finance.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `models_finance`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from backend.enums_finance import EntryKind, GroupMemberRole, GroupType
from backend.models_shared import utc_now, uuid_str


class EntryGroup(Base):
    __tablename__ = "entry_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_type: Mapped[GroupType] = mapped_column(
        Enum(GroupType), nullable=False, index=True
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

    owner_user: Mapped[User] = relationship(
        back_populates="owned_groups",
        foreign_keys=[owner_user_id],
    )
    memberships: Mapped[list[EntryGroupMember]] = relationship(
        back_populates="group",
        foreign_keys="EntryGroupMember.group_id",
        cascade="all, delete-orphan",
    )
    parent_membership: Mapped[EntryGroupMember | None] = relationship(
        back_populates="child_group",
        foreign_keys="EntryGroupMember.child_group_id",
        uselist=False,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
    owned_entities: Mapped[list[Entity]] = relationship(
        back_populates="owner_user",
        foreign_keys="Entity.owner_user_id",
        cascade="all, delete-orphan",
    )
    owned_groups: Mapped[list[EntryGroup]] = relationship(
        back_populates="owner_user", foreign_keys="EntryGroup.owner_user_id"
    )
    owned_tags: Mapped[list[Tag]] = relationship(
        back_populates="owner_user",
        foreign_keys="Tag.owner_user_id",
        cascade="all, delete-orphan",
    )
    owned_taxonomies: Mapped[list[Taxonomy]] = relationship(
        back_populates="owner_user",
        foreign_keys="Taxonomy.owner_user_id",
        cascade="all, delete-orphan",
    )
    filter_groups: Mapped[list[FilterGroup]] = relationship(
        back_populates="owner_user",
        foreign_keys="FilterGroup.owner_user_id",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user",
        foreign_keys="UserSession.user_id",
        cascade="all, delete-orphan",
    )


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_admin_impersonation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    user: Mapped[User] = relationship(back_populates="sessions", foreign_keys=[user_id])


class FilterGroup(Base):
    __tablename__ = "filter_groups"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "key", name="uq_filter_groups_owner_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    owner_user: Mapped[User] = relationship(
        back_populates="filter_groups",
        foreign_keys=[owner_user_id],
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
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
    owner_user: Mapped[User] = relationship(back_populates="accounts")
    entity: Mapped[Entity] = relationship(back_populates="account")

    @property
    def name(self) -> str:
        return self.entity.name if self.entity is not None else ""

    @name.setter
    def name(self, value: str) -> None:
        if self.entity is None:
            raise AttributeError("Account entity must be loaded before setting name")
        self.entity.name = value


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
    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_tags_owner_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
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
    owner_user: Mapped[User] = relationship(
        back_populates="owned_tags",
        foreign_keys=[owner_user_id],
    )


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_entities_owner_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
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
    account: Mapped[Account | None] = relationship(back_populates="entity", uselist=False)
    owner_user: Mapped[User] = relationship(
        back_populates="owned_entities",
        foreign_keys=[owner_user_id],
    )


class Taxonomy(Base):
    __tablename__ = "taxonomies"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "key", name="uq_taxonomies_owner_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
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
    owner_user: Mapped[User] = relationship(
        back_populates="owned_taxonomies",
        foreign_keys=[owner_user_id],
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
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
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

    account: Mapped[Account | None] = relationship(back_populates="entries")
    from_entity_ref: Mapped[Entity | None] = relationship(
        back_populates="as_source_entries",
        foreign_keys=[from_entity_id],
    )
    to_entity_ref: Mapped[Entity | None] = relationship(
        back_populates="as_target_entries",
        foreign_keys=[to_entity_id],
    )
    owner_user: Mapped[User] = relationship(
        back_populates="owned_entries",
        foreign_keys=[owner_user_id],
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary="entry_tags",
        back_populates="entries",
    )
    group_membership: Mapped[EntryGroupMember | None] = relationship(
        back_populates="entry",
        foreign_keys="EntryGroupMember.entry_id",
        uselist=False,
    )


class EntryGroupMember(Base):
    __tablename__ = "entry_group_members"
    __table_args__ = (
        CheckConstraint(
            "(entry_id IS NOT NULL AND child_group_id IS NULL) OR "
            "(entry_id IS NULL AND child_group_id IS NOT NULL)",
            name="ck_entry_group_members_one_subject",
        ),
        CheckConstraint(
            "child_group_id IS NULL OR group_id != child_group_id",
            name="ck_entry_group_members_no_self_child",
        ),
        UniqueConstraint(
            "group_id",
            "entry_id",
            name="uq_entry_group_members_group_entry",
        ),
        UniqueConstraint(
            "group_id",
            "child_group_id",
            name="uq_entry_group_members_group_child",
        ),
        UniqueConstraint("entry_id", name="uq_entry_group_members_entry"),
        UniqueConstraint("child_group_id", name="uq_entry_group_members_child_group"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    group_id: Mapped[str] = mapped_column(
        ForeignKey("entry_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), nullable=True, index=True
    )
    child_group_id: Mapped[str | None] = mapped_column(
        ForeignKey("entry_groups.id", ondelete="CASCADE"), nullable=True, index=True
    )
    member_role: Mapped[GroupMemberRole | None] = mapped_column(
        Enum(GroupMemberRole), nullable=True, index=True
    )
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

    group: Mapped[EntryGroup] = relationship(
        back_populates="memberships",
        foreign_keys=[group_id],
    )
    entry: Mapped[Entry | None] = relationship(
        back_populates="group_membership",
        foreign_keys=[entry_id],
    )
    child_group: Mapped[EntryGroup | None] = relationship(
        back_populates="parent_membership",
        foreign_keys=[child_group_id],
    )

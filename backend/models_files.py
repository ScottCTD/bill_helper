# CALLING SPEC:
# - Purpose: provide the `models_files` module.
# - Inputs: callers that import `backend/models_files.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `models_files`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db_meta import Base
from backend.models_shared import utc_now, uuid_str


class UserFile(Base):
    __tablename__ = "user_files"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "stored_relative_path",
            name="uq_user_files_owner_relative_path",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_area: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    stored_relative_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    attachments: Mapped[list["AgentMessageAttachment"]] = relationship(
        back_populates="user_file",
        passive_deletes=True,
    )

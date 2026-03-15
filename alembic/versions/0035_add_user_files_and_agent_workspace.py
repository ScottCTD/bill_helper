"""add user_files and canonicalize agent attachments

Revision ID: 0035_add_user_files_and_agent_workspace
Revises: 0034_add_entry_tagging_model_to_runtime_settings
Create Date: 2026-03-14 04:30:00.000000
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
from typing import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

from backend.config import get_settings


# revision identifiers, used by Alembic.
revision: str = "0035_add_user_files_and_agent_workspace"
down_revision: str | Sequence[str] | None = "0034_add_entry_tagging_model_to_runtime_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SHA256_BLOCK_SIZE = 1024 * 1024
_USER_FILES_DIRNAME = "user_files"
_UPLOADS_DIRNAME = "uploads"
_ARTIFACTS_DIRNAME = "artifacts"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _user_owner_root(*, data_dir: Path, user_id: str) -> Path:
    return data_dir / _USER_FILES_DIRNAME / user_id


def _ensure_user_roots(*, data_dir: Path, user_id: str) -> Path:
    owner_root = _user_owner_root(data_dir=data_dir, user_id=user_id)
    (owner_root / _UPLOADS_DIRNAME).mkdir(parents=True, exist_ok=True)
    (owner_root / _ARTIFACTS_DIRNAME).mkdir(parents=True, exist_ok=True)
    return owner_root


def _display_name(*, original_filename: str | None, fallback_name: str | None) -> str | None:
    original = Path(" ".join((original_filename or "").split()).strip()).name
    if original:
        return original
    fallback = Path(" ".join((fallback_name or "").split()).strip()).name
    return fallback or None


def _suffix_for_attachment(*, mime_type: str, original_filename: str | None) -> str:
    suffix = Path(original_filename or "").suffix
    if suffix:
        return suffix
    if mime_type == "image/png":
        return ".png"
    if mime_type == "image/jpeg":
        return ".jpg"
    if mime_type == "image/webp":
        return ".webp"
    if mime_type == "application/pdf":
        return ".pdf"
    return ".bin"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(_SHA256_BLOCK_SIZE)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def _cleanup_empty_parent_dirs(path: Path, *, stop_at: Path) -> None:
    current = path.parent
    resolved_stop_at = stop_at.resolve()
    while True:
        try:
            current.rmdir()
        except OSError:
            return
        if current.resolve() == resolved_stop_at:
            return
        if resolved_stop_at not in current.resolve().parents:
            return
        current = current.parent


def _attachment_rows(bind: sa.engine.Connection) -> Iterable[sa.RowMapping]:
    return bind.execute(
        sa.text(
            """
            SELECT
              attachments.id,
              attachments.message_id,
              attachments.mime_type,
              attachments.original_filename,
              attachments.file_path,
              attachments.created_at,
              threads.owner_user_id
            FROM agent_message_attachments AS attachments
            JOIN agent_messages AS messages ON messages.id = attachments.message_id
            JOIN agent_threads AS threads ON threads.id = messages.thread_id
            ORDER BY attachments.created_at ASC, attachments.id ASC
            """
        )
    ).mappings()


def _backfill_user_files(bind: sa.engine.Connection) -> None:
    settings = get_settings()
    data_dir = settings.ensure_data_dir()
    legacy_upload_root = (data_dir / "agent_uploads").resolve()
    for row in _attachment_rows(bind):
        owner_user_id = str(row["owner_user_id"])
        attachment_id = str(row["id"])
        mime_type = str(row["mime_type"])
        original_filename = row["original_filename"]
        source_path = Path(str(row["file_path"]))

        owner_root = _ensure_user_roots(data_dir=data_dir, user_id=owner_user_id)
        target_filename = f"{attachment_id}{_suffix_for_attachment(mime_type=mime_type, original_filename=original_filename)}"
        target_path = owner_root / _UPLOADS_DIRNAME / target_filename
        target_path.parent.mkdir(parents=True, exist_ok=True)

        size_bytes = 0
        sha256: str | None = None
        if source_path.exists():
            shutil.move(str(source_path), str(target_path))
            size_bytes = target_path.stat().st_size
            sha256 = _hash_file(target_path)
            resolved_source = source_path.resolve()
            if legacy_upload_root == resolved_source.parent or legacy_upload_root in resolved_source.parents:
                _cleanup_empty_parent_dirs(resolved_source, stop_at=legacy_upload_root)

        user_file_id = str(uuid4())
        bind.execute(
            sa.text(
                """
                INSERT INTO user_files
                  (
                    id,
                    owner_user_id,
                    storage_area,
                    source_type,
                    stored_relative_path,
                    original_filename,
                    display_name,
                    mime_type,
                    size_bytes,
                    sha256,
                    created_at
                  )
                VALUES
                  (
                    :id,
                    :owner_user_id,
                    :storage_area,
                    :source_type,
                    :stored_relative_path,
                    :original_filename,
                    :display_name,
                    :mime_type,
                    :size_bytes,
                    :sha256,
                    :created_at
                  )
                """
            ),
            {
                "id": user_file_id,
                "owner_user_id": owner_user_id,
                "storage_area": "upload",
                "source_type": "agent_message_attachment",
                "stored_relative_path": str(Path(_UPLOADS_DIRNAME) / target_filename),
                "original_filename": original_filename,
                "display_name": _display_name(
                    original_filename=original_filename,
                    fallback_name=target_filename,
                ),
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "sha256": sha256,
                "created_at": row["created_at"] or _utc_now(),
            },
        )
        bind.execute(
            sa.text(
                """
                UPDATE agent_message_attachments
                SET user_file_id = :user_file_id
                WHERE id = :attachment_id
                """
            ),
            {
                "user_file_id": user_file_id,
                "attachment_id": attachment_id,
            },
        )


def upgrade() -> None:
    op.create_table(
        "user_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("storage_area", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("stored_relative_path", sa.String(length=1024), nullable=False),
        sa.Column("original_filename", sa.String(length=1024), nullable=True),
        sa.Column("display_name", sa.String(length=1024), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "stored_relative_path",
            name="uq_user_files_owner_relative_path",
        ),
    )
    op.create_index(
        op.f("ix_user_files_owner_user_id"),
        "user_files",
        ["owner_user_id"],
        unique=False,
    )

    with op.batch_alter_table("agent_message_attachments") as batch_op:
        batch_op.add_column(sa.Column("user_file_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_agent_message_attachments_user_file_id_user_files",
            "user_files",
            ["user_file_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            op.f("ix_agent_message_attachments_user_file_id"),
            ["user_file_id"],
            unique=False,
        )

    bind = op.get_bind()
    _backfill_user_files(bind)

    with op.batch_alter_table("agent_message_attachments") as batch_op:
        batch_op.alter_column("user_file_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.drop_column("file_path")
        batch_op.drop_column("original_filename")
        batch_op.drop_column("mime_type")


def downgrade() -> None:
    with op.batch_alter_table("agent_message_attachments") as batch_op:
        batch_op.add_column(sa.Column("mime_type", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("original_filename", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("file_path", sa.String(length=1024), nullable=True))

    bind = op.get_bind()
    settings = get_settings()
    data_dir = settings.ensure_data_dir()
    rows = bind.execute(
        sa.text(
            """
            SELECT
              attachments.id,
              attachments.user_file_id,
              files.owner_user_id,
              files.mime_type,
              files.original_filename,
              files.stored_relative_path
            FROM agent_message_attachments AS attachments
            JOIN user_files AS files ON files.id = attachments.user_file_id
            """
        )
    ).mappings()
    for row in rows:
        file_path = (
            _user_owner_root(data_dir=data_dir, user_id=str(row["owner_user_id"]))
            / str(row["stored_relative_path"])
        )
        bind.execute(
            sa.text(
                """
                UPDATE agent_message_attachments
                SET
                  mime_type = :mime_type,
                  original_filename = :original_filename,
                  file_path = :file_path
                WHERE id = :attachment_id
                """
            ),
            {
                "mime_type": row["mime_type"],
                "original_filename": row["original_filename"],
                "file_path": str(file_path),
                "attachment_id": row["id"],
            },
        )

    with op.batch_alter_table("agent_message_attachments") as batch_op:
        batch_op.alter_column("mime_type", existing_type=sa.String(length=255), nullable=False)
        batch_op.alter_column("file_path", existing_type=sa.String(length=1024), nullable=False)
        batch_op.drop_index(op.f("ix_agent_message_attachments_user_file_id"))
        batch_op.drop_constraint(
            "fk_agent_message_attachments_user_file_id_user_files",
            type_="foreignkey",
        )
        batch_op.drop_column("user_file_id")

    op.drop_index(op.f("ix_user_files_owner_user_id"), table_name="user_files")
    op.drop_table("user_files")

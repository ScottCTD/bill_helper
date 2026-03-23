# CALLING SPEC:
# - Purpose: migrate Docling bundle directories to the readable ``uploads/<created-at-date>/<original stem>/raw.<ext>`` layout.
# - Inputs: SQLAlchemy session, bundle-primary ``UserFile`` rows, IANA timezone, optional data dir and dry-run flag.
# - Outputs: status strings per row.
# - Side effects: directory moves, primary-file renames, markdown/image rewrites, and DB updates.
from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models_files import UserFile
from backend.services.agent.agent_attachment_bundle import (
    bundle_directory_segment_for_relocate,
    bundle_upload_date_str_for_created_at,
    is_docling_bundle_primary_stored_path,
    normalize_bundle_relative_path,
    raw_primary_filename,
)
from backend.services.agent.docling_convert import normalize_docling_bundle_outputs
from backend.services.user_files import (
    SOURCE_TYPE_AGENT_ATTACHMENT,
    STORAGE_AREA_UPLOAD,
    UPLOADS_DIRNAME,
    resolve_user_file_path,
    user_upload_root,
    validate_stored_relative_path_for_write,
)


def iter_agent_attachment_bundle_primaries(
    db: Session,
    *,
    owner_user_id: str | None = None,
) -> Iterable[UserFile]:
    stmt = (
        select(UserFile)
        .where(
            UserFile.storage_area == STORAGE_AREA_UPLOAD,
            UserFile.source_type == SOURCE_TYPE_AGENT_ATTACHMENT,
        )
        .order_by(UserFile.owner_user_id.asc(), UserFile.created_at.asc(), UserFile.id.asc())
    )
    if owner_user_id is not None:
        stmt = stmt.where(UserFile.owner_user_id == owner_user_id)
    for row in db.scalars(stmt):
        if is_docling_bundle_primary_stored_path(row.stored_relative_path):
            yield row


def _deduplicated_directory_name(
    *,
    parent_dir: Path,
    desired_name: str,
    ignore_existing_dir: Path,
) -> str:
    candidate = desired_name
    counter = 1
    ignored = ignore_existing_dir.resolve()
    while True:
        path = parent_dir / candidate
        if not path.exists() or path.resolve() == ignored:
            return candidate
        candidate = f"{desired_name} ({counter})"
        counter += 1


def compute_target_stored_relative_path(
    user_file: UserFile,
    *,
    timezone_name: str,
    data_dir: Path | None = None,
) -> str | None:
    """Return desired ``stored_relative_path`` or ``None`` if already correct."""
    normalized = normalize_bundle_relative_path(user_file.stored_relative_path)
    parts = Path(normalized).parts
    if len(parts) != 4 or parts[0] != UPLOADS_DIRNAME:
        return None

    old_primary = resolve_user_file_path(user_file, data_dir=data_dir)
    if not old_primary.exists():
        return None
    old_bundle_dir = old_primary.parent
    want_date = bundle_upload_date_str_for_created_at(
        user_file.created_at,
        timezone_name=timezone_name,
    )
    target_parent = user_upload_root(user_id=user_file.owner_user_id, data_dir=data_dir) / want_date
    target_bundle = _deduplicated_directory_name(
        parent_dir=target_parent,
        desired_name=bundle_directory_segment_for_relocate(
            original_filename=user_file.original_filename,
            mime_type=user_file.mime_type,
        ),
        ignore_existing_dir=old_bundle_dir,
    )
    target_primary = raw_primary_filename(
        original_filename=user_file.original_filename,
        mime_type=user_file.mime_type,
    )
    candidate = normalize_bundle_relative_path(
        str(Path(UPLOADS_DIRNAME) / want_date / target_bundle / target_primary)
    )
    if candidate == normalized:
        return None
    return validate_stored_relative_path_for_write(
        storage_area=STORAGE_AREA_UPLOAD,
        stored_relative_path=candidate,
    )


def _prune_empty_parents(path: Path, *, stop_at: Path) -> None:
    current = path
    resolved_stop = stop_at.resolve()
    while current.resolve() != resolved_stop and current.is_dir():
        try:
            next_up = current.parent
            current.rmdir()
            current = next_up
        except OSError:
            return


def relocate_agent_upload_bundle_primary(
    db: Session,
    *,
    user_file: UserFile,
    timezone_name: str,
    data_dir: Path | None = None,
    dry_run: bool = False,
) -> str:
    current_primary = resolve_user_file_path(user_file, data_dir=data_dir)
    target_rel = compute_target_stored_relative_path(
        user_file,
        timezone_name=timezone_name,
        data_dir=data_dir,
    )
    if target_rel is None:
        if not current_primary.is_file():
            return f"skipped_missing_file:{user_file.id}"
        if dry_run:
            return f"dry_run_normalize:{user_file.id}:{user_file.stored_relative_path}"
        normalize_docling_bundle_outputs(current_primary.parent, primary_filename=current_primary.name)
        return f"normalized:{user_file.id}:{user_file.stored_relative_path}"

    old_norm = normalize_bundle_relative_path(user_file.stored_relative_path)
    old_primary = current_primary
    if not old_primary.is_file():
        return f"skipped_missing_file:{user_file.id}"

    canonical_upload_root = user_upload_root(user_id=user_file.owner_user_id, data_dir=data_dir)
    old_bundle_dir = old_primary.parent
    new_primary = canonical_upload_root.parent / target_rel
    new_bundle_dir = new_primary.parent

    if dry_run:
        return f"dry_run:{user_file.id}:{old_norm}->{target_rel}"

    new_bundle_dir.parent.mkdir(parents=True, exist_ok=True)
    if new_bundle_dir.exists() and new_bundle_dir.resolve() != old_bundle_dir.resolve():
        return f"error_collision:{user_file.id}:{target_rel}"

    shutil.move(str(old_bundle_dir), str(new_bundle_dir))
    migrated_primary = new_bundle_dir / old_primary.name
    if migrated_primary.is_file() and migrated_primary.name != new_primary.name:
        migrated_primary.rename(new_primary)
    normalize_docling_bundle_outputs(new_bundle_dir, primary_filename=new_primary.name)

    old_date_dir = old_bundle_dir.parent
    user_file.stored_relative_path = target_rel
    user_file.size_bytes = new_primary.stat().st_size
    db.flush()
    _prune_empty_parents(old_date_dir, stop_at=canonical_upload_root)
    db.commit()
    return f"relocated:{user_file.id}:{target_rel}"

# CALLING SPEC:
# - Purpose: implement focused service logic for `user_file_workspace_view`.
# - Inputs: callers that import `backend/services/user_file_workspace_view.py` and pass module-defined arguments or framework events.
# - Outputs: helpers that build and maintain the read-only workspace-visible user file mirror.
# - Side effects: filesystem directory resets and symlink creation under the configured data dir.
from __future__ import annotations

import os
from pathlib import Path
import shutil
import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models_files import UserFile
from backend.services.user_files import (
    ARTIFACTS_DIRNAME,
    STORAGE_AREA_ARTIFACT,
    STORAGE_AREA_UPLOAD,
    UPLOADS_DIRNAME,
    display_name_for_file,
    user_file_owner_root,
)

WORKSPACE_VISIBLE_USER_DATA_DIRNAME = "user_data"
_workspace_view_locks: dict[str, threading.RLock] = {}
_workspace_view_locks_guard = threading.Lock()


def user_file_workspace_view_root(
    *,
    user_id: str,
    data_dir: Path | None = None,
) -> Path:
    return user_file_owner_root(user_id=user_id, data_dir=data_dir) / WORKSPACE_VISIBLE_USER_DATA_DIRNAME


def ensure_user_file_workspace_view_root(
    *,
    user_id: str,
    data_dir: Path | None = None,
) -> Path:
    root = user_file_workspace_view_root(user_id=user_id, data_dir=data_dir)
    (root / UPLOADS_DIRNAME).mkdir(parents=True, exist_ok=True)
    (root / ARTIFACTS_DIRNAME).mkdir(parents=True, exist_ok=True)
    return root


def delete_user_file_workspace_view_root(
    *,
    user_id: str,
    data_dir: Path | None = None,
) -> None:
    shutil.rmtree(user_file_workspace_view_root(user_id=user_id, data_dir=data_dir), ignore_errors=True)


def sync_user_file_workspace_view(
    db: Session,
    *,
    user_id: str,
    data_dir: Path | None = None,
) -> Path:
    with _workspace_view_lock(user_id):
        root = ensure_user_file_workspace_view_root(user_id=user_id, data_dir=data_dir)
        canonical_root = user_file_owner_root(user_id=user_id, data_dir=data_dir)
        rows = list(
            db.scalars(
                select(UserFile)
                .where(UserFile.owner_user_id == user_id)
                .order_by(UserFile.storage_area.asc(), UserFile.created_at.asc(), UserFile.id.asc())
            )
        )
        entries_by_area: dict[str, list[UserFile]] = {
            UPLOADS_DIRNAME: [],
            ARTIFACTS_DIRNAME: [],
        }
        for row in rows:
            area_dirname = _workspace_area_dirname(storage_area=row.storage_area)
            entries_by_area[area_dirname].append(row)
        for area_dirname, area_rows in entries_by_area.items():
            _sync_area_directory(
                area_dir=root / area_dirname,
                area_rows=area_rows,
                canonical_root=canonical_root,
            )
        return root


def _sync_area_directory(
    *,
    area_dir: Path,
    area_rows: list[UserFile],
    canonical_root: Path,
) -> None:
    _reset_directory(area_dir)
    used_names: set[str] = set()
    for row in area_rows:
        desired_name = display_name_for_file(
            original_filename=row.display_name or row.original_filename,
            fallback_name=Path(row.stored_relative_path).name,
        ) or Path(row.stored_relative_path).name
        link_name = _unique_link_name(desired_name=desired_name, used_names=used_names)
        used_names.add(link_name.casefold())
        link_path = area_dir / link_name
        target_path = canonical_root / row.stored_relative_path
        if not target_path.exists():
            continue
        relative_target = os.path.relpath(target_path, start=area_dir)
        link_path.unlink(missing_ok=True)
        link_path.symlink_to(relative_target)


def _reset_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for child in directory.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink(missing_ok=True)
            continue
        shutil.rmtree(child, ignore_errors=True)


def _workspace_area_dirname(*, storage_area: str) -> str:
    if storage_area == STORAGE_AREA_UPLOAD:
        return UPLOADS_DIRNAME
    if storage_area == STORAGE_AREA_ARTIFACT:
        return ARTIFACTS_DIRNAME
    raise ValueError(f"Unsupported user file storage area: {storage_area}")


def _unique_link_name(*, desired_name: str, used_names: set[str]) -> str:
    normalized_name = Path(" ".join(desired_name.split()).strip()).name or "file"
    candidate = normalized_name
    suffix = Path(normalized_name).suffix
    stem = normalized_name[: -len(suffix)] if suffix else normalized_name
    counter = 2
    while candidate.casefold() in used_names:
        candidate = f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate
def _workspace_view_lock(user_id: str) -> threading.RLock:
    with _workspace_view_locks_guard:
        existing = _workspace_view_locks.get(user_id)
        if existing is not None:
            return existing
        created = threading.RLock()
        _workspace_view_locks[user_id] = created
        return created

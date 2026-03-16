# CALLING SPEC:
# - Purpose: implement focused service logic for `user_files`.
# - Inputs: callers that import `backend/services/user_files.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `user_files`.
# - Side effects: filesystem writes, file copies/moves, and DB row creation for canonical user files.
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models_files import UserFile
from backend.services.crud_policy import PolicyViolation

USER_FILES_DIRNAME = "user_files"
UPLOADS_DIRNAME = "uploads"
ARTIFACTS_DIRNAME = "artifacts"
STORAGE_AREA_UPLOAD = "upload"
STORAGE_AREA_ARTIFACT = "artifact"
SOURCE_TYPE_AGENT_ATTACHMENT = "agent_message_attachment"
SOURCE_TYPE_WORKSPACE_ARTIFACT = "workspace_artifact"
_SHA256_BLOCK_SIZE = 1024 * 1024


def user_files_root(*, data_dir: Path | None = None) -> Path:
    resolved_data_dir = data_dir or get_settings().data_dir
    return resolved_data_dir / USER_FILES_DIRNAME


def user_file_owner_root(
    *,
    user_id: str,
    data_dir: Path | None = None,
) -> Path:
    return user_files_root(data_dir=data_dir) / user_id


def user_upload_root(
    *,
    user_id: str,
    data_dir: Path | None = None,
) -> Path:
    return user_file_owner_root(user_id=user_id, data_dir=data_dir) / UPLOADS_DIRNAME


def user_artifact_root(
    *,
    user_id: str,
    data_dir: Path | None = None,
) -> Path:
    return user_file_owner_root(user_id=user_id, data_dir=data_dir) / ARTIFACTS_DIRNAME


def ensure_user_file_roots(
    *,
    user_id: str,
    data_dir: Path | None = None,
) -> tuple[Path, Path]:
    from backend.services.user_file_workspace_view import (
        ensure_user_file_workspace_view_root,
    )

    upload_root = user_upload_root(user_id=user_id, data_dir=data_dir)
    artifact_root = user_artifact_root(user_id=user_id, data_dir=data_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)
    ensure_user_file_workspace_view_root(user_id=user_id, data_dir=data_dir)
    return upload_root, artifact_root


def delete_user_file_root(
    *,
    user_id: str,
    data_dir: Path | None = None,
) -> None:
    from backend.services.user_file_workspace_view import (
        delete_user_file_workspace_view_root,
    )

    shutil.rmtree(
        user_file_owner_root(user_id=user_id, data_dir=data_dir), ignore_errors=True
    )
    delete_user_file_workspace_view_root(user_id=user_id, data_dir=data_dir)


def resolve_user_file_path(
    user_file: UserFile,
    *,
    data_dir: Path | None = None,
) -> Path:
    return (
        user_file_owner_root(
            user_id=user_file.owner_user_id,
            data_dir=data_dir,
        )
        / user_file.stored_relative_path
    )


def display_name_for_file(
    *,
    original_filename: str | None,
    fallback_name: str | None = None,
) -> str | None:
    normalized_original = Path(" ".join((original_filename or "").split()).strip()).name
    if normalized_original:
        return normalized_original
    normalized_fallback = Path(" ".join((fallback_name or "").split()).strip()).name
    return normalized_fallback or None


def suffix_for_mime_type(
    *,
    mime_type: str,
    original_filename: str | None,
) -> str:
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


def _relative_path_for_storage_area(
    *,
    storage_area: str,
    stored_filename: str,
) -> str:
    if storage_area == STORAGE_AREA_UPLOAD:
        return str(Path(UPLOADS_DIRNAME) / stored_filename)
    if storage_area == STORAGE_AREA_ARTIFACT:
        return str(Path(ARTIFACTS_DIRNAME) / stored_filename)
    raise PolicyViolation.bad_request(
        f"Unsupported user file storage area: {storage_area}"
    )


def _target_root_for_storage_area(
    *,
    user_id: str,
    storage_area: str,
    data_dir: Path | None = None,
) -> Path:
    if storage_area == STORAGE_AREA_UPLOAD:
        return user_upload_root(user_id=user_id, data_dir=data_dir)
    if storage_area == STORAGE_AREA_ARTIFACT:
        return user_artifact_root(user_id=user_id, data_dir=data_dir)
    raise PolicyViolation.bad_request(
        f"Unsupported user file storage area: {storage_area}"
    )


def _preferred_stored_filename(
    *,
    mime_type: str,
    original_filename: str | None,
    stored_filename: str | None,
) -> str:
    if stored_filename:
        return stored_filename
    return f"{uuid4()}{suffix_for_mime_type(mime_type=mime_type, original_filename=original_filename)}"


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(_SHA256_BLOCK_SIZE)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-",
        dir=str(path.parent),
    )
    temp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def create_user_file_row(
    db: Session,
    *,
    owner_user_id: str,
    storage_area: str,
    source_type: str,
    stored_relative_path: str,
    original_filename: str | None,
    display_name: str | None,
    mime_type: str,
    size_bytes: int,
    sha256: str | None,
) -> UserFile:
    user_file = UserFile(
        owner_user_id=owner_user_id,
        storage_area=storage_area,
        source_type=source_type,
        stored_relative_path=stored_relative_path,
        original_filename=original_filename,
        display_name=display_name,
        mime_type=mime_type,
        size_bytes=size_bytes,
        sha256=sha256,
    )
    db.add(user_file)
    db.flush()
    return user_file


def find_user_file_by_sha256(
    db: Session,
    *,
    user_id: str,
    sha256: str,
    storage_area: str = STORAGE_AREA_UPLOAD,
) -> UserFile | None:
    return (
        db.query(UserFile)
        .filter(
            UserFile.owner_user_id == user_id,
            UserFile.sha256 == sha256,
            UserFile.storage_area == storage_area,
        )
        .first()
    )


def store_user_file_bytes(
    db: Session,
    *,
    owner_user_id: str,
    storage_area: str,
    source_type: str,
    mime_type: str,
    file_bytes: bytes,
    original_filename: str | None,
    display_name: str | None = None,
    stored_filename: str | None = None,
    data_dir: Path | None = None,
) -> UserFile:
    content_hash = _hash_bytes(file_bytes)
    existing = find_user_file_by_sha256(
        db,
        user_id=owner_user_id,
        sha256=content_hash,
        storage_area=storage_area,
    )
    if existing is not None:
        return existing

    target_root = _target_root_for_storage_area(
        user_id=owner_user_id,
        storage_area=storage_area,
        data_dir=data_dir,
    )
    target_root.mkdir(parents=True, exist_ok=True)
    resolved_stored_filename = _preferred_stored_filename(
        mime_type=mime_type,
        original_filename=original_filename,
        stored_filename=stored_filename,
    )
    target_path = target_root / resolved_stored_filename
    _atomic_write_bytes(target_path, file_bytes)
    relative_path = _relative_path_for_storage_area(
        storage_area=storage_area,
        stored_filename=resolved_stored_filename,
    )
    user_file = create_user_file_row(
        db,
        owner_user_id=owner_user_id,
        storage_area=storage_area,
        source_type=source_type,
        stored_relative_path=relative_path,
        original_filename=original_filename,
        display_name=display_name
        or display_name_for_file(
            original_filename=original_filename,
            fallback_name=resolved_stored_filename,
        ),
        mime_type=mime_type,
        size_bytes=len(file_bytes),
        sha256=content_hash,
    )
    from backend.services.user_file_workspace_view import sync_user_file_workspace_view

    sync_user_file_workspace_view(db, user_id=owner_user_id, data_dir=data_dir)
    return user_file


def import_user_file_from_path(
    db: Session,
    *,
    owner_user_id: str,
    storage_area: str,
    source_type: str,
    source_path: Path,
    mime_type: str,
    original_filename: str | None,
    display_name: str | None = None,
    stored_filename: str | None = None,
    move_source: bool = False,
    data_dir: Path | None = None,
) -> UserFile:
    if not source_path.exists():
        raise PolicyViolation.not_found(f"Source file does not exist: {source_path}")

    target_root = _target_root_for_storage_area(
        user_id=owner_user_id,
        storage_area=storage_area,
        data_dir=data_dir,
    )
    target_root.mkdir(parents=True, exist_ok=True)
    resolved_stored_filename = _preferred_stored_filename(
        mime_type=mime_type,
        original_filename=original_filename,
        stored_filename=stored_filename,
    )
    target_path = target_root / resolved_stored_filename
    if move_source:
        shutil.move(str(source_path), str(target_path))
    else:
        shutil.copy2(source_path, target_path)

    relative_path = _relative_path_for_storage_area(
        storage_area=storage_area,
        stored_filename=resolved_stored_filename,
    )
    user_file = create_user_file_row(
        db,
        owner_user_id=owner_user_id,
        storage_area=storage_area,
        source_type=source_type,
        stored_relative_path=relative_path,
        original_filename=original_filename,
        display_name=display_name
        or display_name_for_file(
            original_filename=original_filename,
            fallback_name=source_path.name,
        ),
        mime_type=mime_type,
        size_bytes=target_path.stat().st_size,
        sha256=_hash_file(target_path),
    )
    from backend.services.user_file_workspace_view import sync_user_file_workspace_view

    sync_user_file_workspace_view(db, user_id=owner_user_id, data_dir=data_dir)
    return user_file


def promote_workspace_file_to_artifact(
    db: Session,
    *,
    owner_user_id: str,
    workspace_file_path: Path,
    mime_type: str,
    original_filename: str | None = None,
    display_name: str | None = None,
    source_type: str = SOURCE_TYPE_WORKSPACE_ARTIFACT,
    stored_filename: str | None = None,
    data_dir: Path | None = None,
) -> UserFile:
    return import_user_file_from_path(
        db,
        owner_user_id=owner_user_id,
        storage_area=STORAGE_AREA_ARTIFACT,
        source_type=source_type,
        source_path=workspace_file_path,
        mime_type=mime_type,
        original_filename=original_filename or workspace_file_path.name,
        display_name=display_name,
        stored_filename=stored_filename,
        move_source=False,
        data_dir=data_dir,
    )

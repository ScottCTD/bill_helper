# CALLING SPEC:
# - Purpose: write agent PDF/image uploads into dated readable bundle dirs, run Docling, and register ``UserFile`` rows.
# - Inputs: raw bytes, mime type, original filename, owner user id, optional data dir and timezone name.
# - Outputs: ``UserFile`` for the primary uploaded file path.
# - Side effects: canonical filesystem writes and Docling artifact generation inside the upload bundle.
from __future__ import annotations

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.models_files import UserFile
from backend.services.agent.docling_convert import convert_upload_bundle_source
from backend.services.crud_policy import PolicyViolation
from backend.services.user_files import (
    SOURCE_TYPE_AGENT_ATTACHMENT,
    STORAGE_AREA_UPLOAD,
    UPLOADS_DIRNAME,
    create_user_file_for_existing_canonical_path,
    suffix_for_mime_type,
    user_upload_root,
    write_canonical_bytes_at_relative_path,
)

_BUNDLE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _replace_path_breaking_characters(value: str) -> str:
    cleaned: list[str] = []
    for char in value:
        codepoint = ord(char)
        if char in {"/", "\\"} or codepoint == 0 or codepoint < 32 or codepoint == 127:
            cleaned.append("_")
            continue
        cleaned.append(char)
    return "".join(cleaned)


def _safe_upload_basename(*, original_filename: str | None, mime_type: str) -> str:
    raw = (original_filename or "").replace("\\", "/").split("/")[-1]
    sanitized = _replace_path_breaking_characters(raw)
    if not sanitized or sanitized in {".", ".."}:
        sanitized = "upload"
    if not Path(sanitized).suffix:
        sanitized = f"{sanitized}{suffix_for_mime_type(mime_type=mime_type, original_filename=original_filename)}"
    return sanitized


def bundle_directory_segment_for_upload(
    *,
    original_filename: str | None,
    mime_type: str,
) -> str:
    basename = _safe_upload_basename(original_filename=original_filename, mime_type=mime_type)
    stem = _replace_path_breaking_characters(Path(basename).stem)
    if not stem or stem in {".", ".."}:
        return "upload"
    return stem


def bundle_directory_segment_for_relocate(
    *,
    original_filename: str | None,
    mime_type: str,
) -> str:
    return bundle_directory_segment_for_upload(
        original_filename=original_filename,
        mime_type=mime_type,
    )


def raw_primary_filename(*, original_filename: str | None, mime_type: str) -> str:
    suffix = suffix_for_mime_type(mime_type=mime_type, original_filename=original_filename)
    return f"raw{suffix}"


def _deduplicated_directory_name(
    *,
    parent_dir: Path,
    desired_name: str,
    ignore_existing_dir: Path | None = None,
) -> str:
    candidate = desired_name
    counter = 1
    ignored = ignore_existing_dir.resolve() if ignore_existing_dir is not None else None
    while True:
        path = parent_dir / candidate
        if not path.exists():
            return candidate
        if ignored is not None and path.resolve() == ignored:
            return candidate
        candidate = f"{desired_name} ({counter})"
        counter += 1


def build_agent_upload_stored_relative_path(
    *,
    owner_user_id: str,
    original_filename: str | None,
    mime_type: str,
    timezone_name: str,
    data_dir: Path | None = None,
) -> str:
    """Return ``uploads/YYYY-MM-DD/<bundle_dir>/raw.<ext>`` for a new bundle."""
    try:
        tz = ZoneInfo(timezone_name)
    except Exception as exc:
        raise PolicyViolation.bad_request("Invalid timezone configuration.") from exc
    date_str = datetime.now(tz).strftime("%Y-%m-%d")
    if not _BUNDLE_DATE_RE.match(date_str):
        raise PolicyViolation.bad_request("Invalid bundle date segment.")
    date_root = user_upload_root(user_id=owner_user_id, data_dir=data_dir) / date_str
    bundle_dir = _deduplicated_directory_name(
        parent_dir=date_root,
        desired_name=bundle_directory_segment_for_upload(
            original_filename=original_filename,
            mime_type=mime_type,
        ),
    )
    primary = raw_primary_filename(original_filename=original_filename, mime_type=mime_type)
    return f"{UPLOADS_DIRNAME}/{date_str}/{bundle_dir}/{primary}"


def ingest_agent_attachment_with_docling(
    db: Session,
    *,
    owner_user_id: str,
    file_bytes: bytes,
    mime_type: str,
    original_filename: str | None,
    timezone_name: str,
    data_dir: Path | None = None,
) -> UserFile:
    """Persist upload under a new readable bundle directory, run Docling, and register the primary."""
    mime = (mime_type or "").lower()
    is_pdf = mime == "application/pdf"
    is_image = mime.startswith("image/")
    if not (is_pdf or is_image):
        raise PolicyViolation.bad_request("Only PDF and image attachments are supported.")

    rel = build_agent_upload_stored_relative_path(
        owner_user_id=owner_user_id,
        original_filename=original_filename,
        mime_type=mime,
        timezone_name=timezone_name,
        data_dir=data_dir,
    )
    primary_path = write_canonical_bytes_at_relative_path(
        owner_user_id=owner_user_id,
        storage_area=STORAGE_AREA_UPLOAD,
        stored_relative_path=rel,
        file_bytes=file_bytes,
        data_dir=data_dir,
    )
    try:
        convert_upload_bundle_source(primary_path, is_pdf=is_pdf)
    except Exception:
        shutil.rmtree(primary_path.parent, ignore_errors=True)
        raise

    return create_user_file_for_existing_canonical_path(
        db,
        owner_user_id=owner_user_id,
        storage_area=STORAGE_AREA_UPLOAD,
        source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
        stored_relative_path=rel,
        original_filename=original_filename,
        display_name=None,
        mime_type=mime_type,
        data_dir=data_dir,
    )


def normalize_bundle_relative_path(stored_relative_path: str) -> str:
    return str(Path(stored_relative_path)).replace("\\", "/")


def is_docling_bundle_primary_stored_path(stored_relative_path: str) -> bool:
    """True if path matches ``uploads/YYYY-MM-DD/<bundle>/<file>`` layout."""
    parts = Path(normalize_bundle_relative_path(stored_relative_path)).parts
    if len(parts) != 4:
        return False
    if parts[0] != UPLOADS_DIRNAME:
        return False
    return bool(_BUNDLE_DATE_RE.match(parts[1]))


def bundle_upload_date_str_for_created_at(created_at: datetime, *, timezone_name: str) -> str:
    """Calendar date for ``uploads/YYYY-MM-DD/`` from stored ``created_at`` in the given IANA zone."""
    try:
        tz = ZoneInfo(timezone_name)
    except Exception as exc:
        raise PolicyViolation.bad_request("Invalid timezone configuration.") from exc
    aware = created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=UTC)
    date_str = aware.astimezone(tz).strftime("%Y-%m-%d")
    if not _BUNDLE_DATE_RE.match(date_str):
        raise PolicyViolation.bad_request("Invalid derived bundle date segment.")
    return date_str


def workspace_uploads_prefix_for_primary_stored_path(stored_relative_path: str) -> str | None:
    """Return ``/workspace/uploads/YYYY-MM-DD/<bundle_dir>`` for bundle primaries."""
    if not is_docling_bundle_primary_stored_path(stored_relative_path):
        return None
    parts = Path(normalize_bundle_relative_path(stored_relative_path)).parts
    return f"/workspace/{parts[0]}/{parts[1]}/{parts[2]}"

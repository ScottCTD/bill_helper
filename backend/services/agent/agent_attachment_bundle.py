# CALLING SPEC:
# - Purpose: write agent PDF/image uploads into dated readable bundle dirs, run Docling, and register ``UserFile`` rows.
# - Inputs: raw bytes, mime type, original filename, owner user id, optional data dir and timezone name.
# - Outputs: ``UserFile`` for the primary uploaded file path.
# - Side effects: canonical filesystem writes and Docling artifact generation inside the upload bundle.
from __future__ import annotations

import hashlib
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pymupdf
from sqlalchemy.orm import Session

from backend.models_files import UserFile
from backend.services.agent.docling_convert import convert_upload_bundle_source
from backend.services.crud_policy import PolicyViolation
from backend.services.user_files import (
    SOURCE_TYPE_AGENT_ATTACHMENT,
    STORAGE_AREA_UPLOAD,
    UPLOADS_DIRNAME,
    create_user_file_for_existing_canonical_path,
    find_user_file_by_sha256,
    resolve_user_file_path,
    suffix_for_mime_type,
    user_file_owner_root,
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


def _hash_bytes(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def _copy_existing_bundle_to_new_relative_path(
    *,
    existing_user_file: UserFile,
    new_relative_path: str,
    data_dir: Path | None = None,
) -> Path:
    source_primary = resolve_user_file_path(existing_user_file, data_dir=data_dir)
    source_bundle_dir = source_primary.parent
    target_primary = user_file_owner_root(
        user_id=existing_user_file.owner_user_id,
        data_dir=data_dir,
    ) / new_relative_path
    target_bundle_dir = target_primary.parent
    shutil.copytree(source_bundle_dir, target_bundle_dir)
    return target_primary


def _bundle_has_docling_output(
    user_file: UserFile,
    *,
    data_dir: Path | None = None,
) -> bool:
    primary_path = resolve_user_file_path(user_file, data_dir=data_dir)
    return primary_path.parent.joinpath("parsed.md").is_file()


def _bundle_has_pdf_page_images(
    user_file: UserFile,
    *,
    data_dir: Path | None = None,
) -> bool:
    primary_path = resolve_user_file_path(user_file, data_dir=data_dir)
    bundle_dir = primary_path.parent
    return any(
        path.is_file() and path.name != primary_path.name and path.suffix.lower() == ".png"
        for path in bundle_dir.iterdir()
    )


def duplicate_agent_attachment_from_existing_bundle(
    db: Session,
    *,
    existing_user_file: UserFile,
    owner_user_id: str,
    original_filename: str | None,
    timezone_name: str,
    data_dir: Path | None = None,
) -> UserFile:
    rel = build_agent_upload_stored_relative_path(
        owner_user_id=owner_user_id,
        original_filename=original_filename,
        mime_type=existing_user_file.mime_type,
        timezone_name=timezone_name,
        data_dir=data_dir,
    )
    copied_primary: Path | None = None
    try:
        copied_primary = _copy_existing_bundle_to_new_relative_path(
            existing_user_file=existing_user_file,
            new_relative_path=rel,
            data_dir=data_dir,
        )
        return create_user_file_for_existing_canonical_path(
            db,
            owner_user_id=owner_user_id,
            storage_area=STORAGE_AREA_UPLOAD,
            source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
            stored_relative_path=rel,
            original_filename=original_filename,
            display_name=None,
            mime_type=existing_user_file.mime_type,
            data_dir=data_dir,
        )
    except Exception:
        if copied_primary is not None:
            shutil.rmtree(copied_primary.parent, ignore_errors=True)
        raise


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

    content_hash = _hash_bytes(file_bytes)
    existing = find_user_file_by_sha256(
        db,
        user_id=owner_user_id,
        sha256=content_hash,
        storage_area=STORAGE_AREA_UPLOAD,
    )
    if (
        existing is not None
        and existing.source_type == SOURCE_TYPE_AGENT_ATTACHMENT
        and existing.mime_type == mime
        and _bundle_has_docling_output(existing, data_dir=data_dir)
    ):
        return duplicate_agent_attachment_from_existing_bundle(
            db,
            existing_user_file=existing,
            owner_user_id=owner_user_id,
            original_filename=original_filename,
            timezone_name=timezone_name,
            data_dir=data_dir,
        )

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


def pdf_pages_as_png_bytes(primary_path: Path) -> list[bytes]:
    """Render each PDF page to PNG bytes (same scale as on-disk ``page-*.png`` bundles).

    Uses PyMuPDF scale 2× over the default 72 pt/in raster (~144 dpi).
    """
    document = pymupdf.open(primary_path)
    try:
        rendered: list[bytes] = []
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            rendered.append(pixmap.tobytes("png"))
        return rendered
    finally:
        document.close()


def _render_pdf_pages_without_ocr(primary_path: Path) -> None:
    parent = primary_path.parent
    for index, png_bytes in enumerate(pdf_pages_as_png_bytes(primary_path), start=1):
        (parent / f"page-{index}.png").write_bytes(png_bytes)


def ingest_agent_attachment_without_docling(
    db: Session,
    *,
    owner_user_id: str,
    file_bytes: bytes,
    mime_type: str,
    original_filename: str | None,
    timezone_name: str,
    data_dir: Path | None = None,
) -> UserFile:
    mime = (mime_type or "").lower()
    is_pdf = mime == "application/pdf"
    is_image = mime.startswith("image/")
    if not (is_pdf or is_image):
        raise PolicyViolation.bad_request("Only PDF and image attachments are supported.")

    content_hash = _hash_bytes(file_bytes)
    existing = find_user_file_by_sha256(
        db,
        user_id=owner_user_id,
        sha256=content_hash,
        storage_area=STORAGE_AREA_UPLOAD,
    )
    if existing is not None and existing.source_type == SOURCE_TYPE_AGENT_ATTACHMENT and existing.mime_type == mime:
        if is_image or _bundle_has_pdf_page_images(existing, data_dir=data_dir) or _bundle_has_docling_output(existing, data_dir=data_dir):
            return duplicate_agent_attachment_from_existing_bundle(
                db,
                existing_user_file=existing,
                owner_user_id=owner_user_id,
                original_filename=original_filename,
                timezone_name=timezone_name,
                data_dir=data_dir,
            )

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
        if is_pdf:
            _render_pdf_pages_without_ocr(primary_path)
    except Exception:
        shutil.rmtree(primary_path.parent, ignore_errors=True)
        raise RuntimeError("Document conversion failed.")

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

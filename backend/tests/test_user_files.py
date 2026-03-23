from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import backend.models_agent  # noqa: F401
import backend.models_files  # noqa: F401
import backend.models_finance  # noqa: F401
import backend.models_settings  # noqa: F401
from backend.config import get_settings
from backend.db_meta import Base
from backend.models_files import UserFile
from backend.services.agent.agent_upload_bundle_relocate import (
    relocate_agent_upload_bundle_primary,
)
from backend.services.user_files import (
    SOURCE_TYPE_AGENT_ATTACHMENT,
    STORAGE_AREA_UPLOAD,
    create_user_file_for_existing_canonical_path,
    resolve_user_file_path,
    store_user_file_bytes,
    user_file_owner_root,
)
from backend.services.users import create_user_with_unique_name


def _session_for_tmp_db(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'user-files.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_store_user_file_bytes_writes_canonical_upload_and_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("BILL_HELPER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BILL_HELPER_AGENT_WORKSPACE_ENABLED", "0")
    get_settings.cache_clear()

    db = _session_for_tmp_db(tmp_path)
    try:
        user = create_user_with_unique_name(
            db,
            raw_name="alice",
            password="alice-password",
        )
        user_file = store_user_file_bytes(
            db,
            owner_user_id=user.id,
            storage_area=STORAGE_AREA_UPLOAD,
            source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
            mime_type="image/png",
            file_bytes=b"\x89PNG\r\n\x1a\n",
            original_filename="receipt.png",
        )
        db.commit()

        absolute_path = resolve_user_file_path(user_file)
        assert absolute_path.exists()
        assert user_file.stored_relative_path.startswith("uploads/")
        assert user_file.size_bytes == 8
        assert user_file.sha256
        assert absolute_path.read_bytes() == b"\x89PNG\r\n\x1a\n"
    finally:
        db.close()
        get_settings.cache_clear()


def test_store_user_file_bytes_deduplicates_by_sha256(tmp_path, monkeypatch):
    monkeypatch.setenv("BILL_HELPER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BILL_HELPER_AGENT_WORKSPACE_ENABLED", "0")
    get_settings.cache_clear()

    db = _session_for_tmp_db(tmp_path)
    try:
        user = create_user_with_unique_name(
            db,
            raw_name="alice",
            password="alice-password",
        )
        content = b"\x89PNG\r\n\x1a\nduplicate-content"
        first = store_user_file_bytes(
            db,
            owner_user_id=user.id,
            storage_area=STORAGE_AREA_UPLOAD,
            source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
            mime_type="image/png",
            file_bytes=content,
            original_filename="first.png",
        )
        db.commit()

        second = store_user_file_bytes(
            db,
            owner_user_id=user.id,
            storage_area=STORAGE_AREA_UPLOAD,
            source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
            mime_type="image/png",
            file_bytes=content,
            original_filename="second.png",
        )
        db.commit()

        assert first.id == second.id
        assert first.sha256 == second.sha256
        assert first.original_filename == "first.png"
    finally:
        db.close()
        get_settings.cache_clear()


def test_create_user_file_for_existing_canonical_bundle_primary(tmp_path, monkeypatch):
    monkeypatch.setenv("BILL_HELPER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BILL_HELPER_AGENT_WORKSPACE_ENABLED", "0")
    get_settings.cache_clear()

    db = _session_for_tmp_db(tmp_path)
    try:
        user = create_user_with_unique_name(
            db,
            raw_name="bundle-user",
            password="bundle-user-password",
        )
        owner = user_file_owner_root(user_id=user.id, data_dir=tmp_path / "data")
        bundle = owner / "uploads" / "2026-01-20" / "Statement March"
        bundle.mkdir(parents=True)
        primary = bundle / "raw.pdf"
        primary.write_bytes(b"%PDF-1.4 bundle")
        (bundle / "parsed.md").write_text("# bundle-md\n", encoding="utf-8")

        row = create_user_file_for_existing_canonical_path(
            db,
            owner_user_id=user.id,
            storage_area=STORAGE_AREA_UPLOAD,
            source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
            stored_relative_path="uploads/2026-01-20/Statement March/raw.pdf",
            original_filename="Statement March.pdf",
            display_name=None,
            mime_type="application/pdf",
            data_dir=tmp_path / "data",
        )
        db.commit()

        assert resolve_user_file_path(row, data_dir=tmp_path / "data") == primary
    finally:
        db.close()
        get_settings.cache_clear()


def test_relocate_agent_upload_bundle_primary_moves_to_readable_raw_layout(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("BILL_HELPER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BILL_HELPER_AGENT_WORKSPACE_ENABLED", "0")
    get_settings.cache_clear()

    db_path = tmp_path / "user-files.sqlite"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    db = session_factory()
    try:
        user = create_user_with_unique_name(
            db,
            raw_name="relocate-user",
            password="relocate-user-password",
        )
        data_dir = tmp_path / "data"
        owner = user_file_owner_root(user_id=user.id, data_dir=data_dir)
        bundle = owner / "uploads" / "2026-03-22" / "abcdabcdabcd"
        bundle.mkdir(parents=True)
        (bundle / "stmt.pdf").write_bytes(b"%PDF-1.4")
        (bundle / "statement-fig.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (bundle / "parsed.md").write_text("# md\n\n![](statement-fig.png)\n", encoding="utf-8")
        user_file = create_user_file_for_existing_canonical_path(
            db,
            owner_user_id=user.id,
            storage_area=STORAGE_AREA_UPLOAD,
            source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
            stored_relative_path="uploads/2026-03-22/abcdabcdabcd/stmt.pdf",
            original_filename="Statement March.pdf",
            display_name=None,
            mime_type="application/pdf",
            data_dir=data_dir,
        )
        user_file.created_at = datetime(2025, 11, 5, 15, 0, 0, tzinfo=UTC)
        db.commit()

        status = relocate_agent_upload_bundle_primary(
            db,
            user_file=user_file,
            timezone_name="UTC",
            data_dir=data_dir,
            dry_run=False,
        )
        assert status.startswith("relocated:")
    finally:
        db.close()

    db2 = session_factory()
    try:
        row = db2.get(UserFile, user_file.id)
        assert row is not None
        assert row.stored_relative_path == "uploads/2025-11-05/Statement March/raw.pdf"
        new_primary = resolve_user_file_path(row, data_dir=data_dir)
        assert new_primary.is_file()
        assert new_primary.name == "raw.pdf"
        parsed = new_primary.parent / "parsed.md"
        assert parsed.is_file()
        assert "figure-1.png" in parsed.read_text(encoding="utf-8")
        assert (new_primary.parent / "figure-1.png").is_file()
        assert not bundle.exists()
    finally:
        db2.close()
        get_settings.cache_clear()

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import backend.models_agent  # noqa: F401
import backend.models_files  # noqa: F401
import backend.models_finance  # noqa: F401
import backend.models_settings  # noqa: F401
from backend.config import get_settings
from backend.contracts_users import UserCreateCommand
from backend.db_meta import Base
from backend.services.user_files import (
    SOURCE_TYPE_AGENT_ATTACHMENT,
    STORAGE_AREA_ARTIFACT,
    STORAGE_AREA_UPLOAD,
    promote_workspace_file_to_artifact,
    resolve_user_file_path,
    store_user_file_bytes,
    user_file_owner_root,
)
from backend.services.user_file_workspace_view import sync_user_file_workspace_view, user_file_workspace_view_root
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


def test_promote_workspace_file_to_artifact_copies_workspace_file(tmp_path, monkeypatch):
    monkeypatch.setenv("BILL_HELPER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BILL_HELPER_AGENT_WORKSPACE_ENABLED", "0")
    get_settings.cache_clear()

    workspace_source = tmp_path / "workspace-output.txt"
    workspace_source.write_text("artifact-ready", encoding="utf-8")

    db = _session_for_tmp_db(tmp_path)
    try:
        user = create_user_with_unique_name(
            db,
            raw_name="alice",
            password="alice-password",
        )
        artifact = promote_workspace_file_to_artifact(
            db,
            owner_user_id=user.id,
            workspace_file_path=workspace_source,
            mime_type="text/plain",
            original_filename="report.txt",
        )
        db.commit()

        absolute_path = resolve_user_file_path(artifact)
        assert artifact.storage_area == STORAGE_AREA_ARTIFACT
        assert artifact.stored_relative_path.startswith("artifacts/")
        assert workspace_source.exists()
        assert absolute_path.exists()
        assert absolute_path.read_text(encoding="utf-8") == "artifact-ready"
    finally:
        db.close()
        get_settings.cache_clear()


def test_workspace_view_uses_display_names_and_disambiguates_duplicates(tmp_path, monkeypatch):
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
        store_user_file_bytes(
            db,
            owner_user_id=user.id,
            storage_area=STORAGE_AREA_UPLOAD,
            source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
            mime_type="application/pdf",
            file_bytes=b"%PDF-1.4\nfirst\n",
            original_filename="statement.pdf",
            stored_filename="a.pdf",
        )
        store_user_file_bytes(
            db,
            owner_user_id=user.id,
            storage_area=STORAGE_AREA_UPLOAD,
            source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
            mime_type="application/pdf",
            file_bytes=b"%PDF-1.4\nsecond\n",
            original_filename="statement.pdf",
            stored_filename="b.pdf",
        )
        db.commit()

        view_root = sync_user_file_workspace_view(db, user_id=user.id)
        upload_names = sorted(path.name for path in (view_root / "uploads").iterdir())
        assert view_root == user_file_owner_root(user_id=user.id, data_dir=tmp_path / "data") / "user_data"
        assert upload_names == ["statement (2).pdf", "statement.pdf"]
        assert (view_root / "uploads" / "statement.pdf").is_symlink()
        assert (view_root / "uploads" / "statement.pdf").readlink().as_posix() == "../../uploads/a.pdf"
    finally:
        db.close()
        get_settings.cache_clear()


def test_workspace_view_sync_is_safe_to_repeat_for_existing_links(tmp_path, monkeypatch):
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
        store_user_file_bytes(
            db,
            owner_user_id=user.id,
            storage_area=STORAGE_AREA_UPLOAD,
            source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
            mime_type="application/pdf",
            file_bytes=b"%PDF-1.4\nrepeat\n",
            original_filename="statement.pdf",
            stored_filename="repeat.pdf",
        )
        db.commit()

        first_root = sync_user_file_workspace_view(db, user_id=user.id)
        second_root = sync_user_file_workspace_view(db, user_id=user.id)

        assert first_root == second_root
        assert sorted(path.name for path in (second_root / "uploads").iterdir()) == ["statement.pdf"]
        assert (second_root / "uploads" / "statement.pdf").is_symlink()
    finally:
        db.close()
        get_settings.cache_clear()

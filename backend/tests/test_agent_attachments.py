from __future__ import annotations

from datetime import UTC, datetime

from backend.services.agent.agent_attachment_bundle import (
    build_agent_upload_stored_relative_path,
    bundle_directory_segment_for_relocate,
    bundle_upload_date_str_for_created_at,
    is_docling_bundle_primary_stored_path,
    workspace_uploads_prefix_for_primary_stored_path,
)


def test_build_agent_upload_stored_relative_path_shape(tmp_path) -> None:
    rel = build_agent_upload_stored_relative_path(
        owner_user_id="user-1",
        original_filename="My Stmt.pdf",
        mime_type="application/pdf",
        timezone_name="UTC",
        data_dir=tmp_path,
    )
    parts = rel.split("/")
    assert len(parts) == 4
    assert parts[0] == "uploads"
    assert len(parts[1]) == 10 and parts[1][4] == "-"
    assert parts[2] == "My Stmt"
    assert parts[3] == "raw.pdf"


def test_build_agent_upload_stored_relative_path_deduplicates_with_suffix(tmp_path) -> None:
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    parent = tmp_path / "user_files" / "user-1" / "uploads" / date_str / "My Stmt"
    parent.mkdir(parents=True)
    rel = build_agent_upload_stored_relative_path(
        owner_user_id="user-1",
        original_filename="My Stmt.pdf",
        mime_type="application/pdf",
        timezone_name="UTC",
        data_dir=tmp_path,
    )
    assert rel.endswith("/My Stmt (1)/raw.pdf")


def test_bundle_directory_segment_for_relocate_preserves_visible_stem() -> None:
    assert (
        bundle_directory_segment_for_relocate(
            original_filename="My Stmt.pdf",
            mime_type="application/pdf",
        )
        == "My Stmt"
    )


def test_bundle_upload_date_str_for_created_at_respects_timezone() -> None:
    ts = datetime(2025, 11, 5, 7, 0, 0, tzinfo=UTC)
    assert bundle_upload_date_str_for_created_at(ts, timezone_name="America/Toronto") == "2025-11-05"


def test_is_docling_bundle_primary_stored_path_detects_bundles() -> None:
    assert is_docling_bundle_primary_stored_path(
        "uploads/2026-03-22/February Statement/raw.pdf"
    )
    assert not is_docling_bundle_primary_stored_path("uploads/flat-uuid.pdf")


def test_workspace_uploads_prefix_for_primary_stored_path_returns_absolute_workspace_path() -> None:
    assert (
        workspace_uploads_prefix_for_primary_stored_path(
            "uploads/2026-03-22/February Statement/raw.pdf"
        )
        == "/workspace/uploads/2026-03-22/February Statement"
    )

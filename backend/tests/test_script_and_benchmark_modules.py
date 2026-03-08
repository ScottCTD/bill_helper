from __future__ import annotations

import json
from pathlib import Path


def test_snapshot_module_create_list_and_restore(tmp_path, monkeypatch):
    from benchmark import snapshot as snapshot_module

    snapshots_dir = tmp_path / "snapshots"
    monkeypatch.setattr(snapshot_module, "SNAPSHOTS_DIR", snapshots_dir)

    source_db = tmp_path / "source.sqlite3"
    source_db.write_bytes(b"seed-db")

    snapshot_dir = snapshot_module.create_snapshot("default", source_db=source_db)
    assert snapshot_dir == snapshots_dir / "default"
    assert (snapshot_dir / "db.sqlite3").exists()
    assert (snapshot_dir / "metadata.json").exists()

    listed = snapshot_module.list_snapshots()
    assert len(listed) == 1
    assert listed[0]["name"] == "default"
    assert listed[0]["has_db"] is True

    production_db = tmp_path / "data" / "bill_helper.db"
    monkeypatch.setattr(snapshot_module, "_production_db_path", lambda: production_db)
    snapshot_module.restore_snapshot("default")
    assert production_db.read_bytes() == source_db.read_bytes()


def test_generate_ground_truth_writes_draft_file_when_ground_truth_exists(tmp_path, monkeypatch):
    from benchmark import generate_ground_truth as gt_module

    case_id = "case_001"
    run_id = "run_abc"
    cases_dir = tmp_path / "cases"
    results_dir = tmp_path / "results"
    case_dir = cases_dir / case_id
    case_dir.mkdir(parents=True)
    (case_dir / "input.json").write_text("{}", encoding="utf-8")
    (case_dir / "ground_truth.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(gt_module, "CASES_DIR", cases_dir)
    monkeypatch.setattr(gt_module, "RESULTS_DIR", results_dir)

    def fake_run_benchmark(model_name: str, case_ids: list[str], workers: int) -> str:
        assert model_name == "model/test"
        assert case_ids == [case_id]
        assert workers == 1
        out_path = results_dir / run_id / "cases" / case_id
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / "results.json").write_text(
            json.dumps(
                {
                    "tags": [{"name": "food", "type": "expense"}],
                    "entities": [{"name": "merchant", "category": "merchant"}],
                    "entries": [
                        {
                            "kind": "EXPENSE",
                            "date": "2026-01-01",
                            "name": "Coffee",
                            "amount_minor": 500,
                            "currency_code": "CAD",
                            "from_entity": "Demo Debit",
                            "to_entity": "Merchant",
                            "tags": ["food"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return run_id

    monkeypatch.setattr(gt_module, "run_benchmark", fake_run_benchmark)
    result = gt_module.generate_ground_truth(case_id, "model/test")

    assert result.run_id == run_id
    assert result.wrote_draft_path is True
    assert result.output_path.name == "ground_truth_draft.json"
    assert result.output_path.exists()


def test_create_empty_snapshot_writes_metadata_and_invokes_stamp(tmp_path, monkeypatch):
    from benchmark import create_empty_snapshot as create_snapshot_module

    snap_dir = tmp_path / "benchmark" / "fixtures" / "snapshots" / "default"
    monkeypatch.setattr(create_snapshot_module, "SNAP_DIR", snap_dir)
    monkeypatch.setattr(create_snapshot_module, "build_engine_for_url", lambda _url: object())
    monkeypatch.setattr(create_snapshot_module, "build_session_maker", lambda _engine: lambda: None)

    monkeypatch.setattr(
        create_snapshot_module,
        "seed_all",
        lambda _db, include_user_memory: {
            "user": "admin",
            "accounts": ["Scotiabank Debit", "Scotiabank Credit"],
            "tags": 3,
            "entity_categories": 2,
            "user_memory": True,
        },
    )

    stamped_paths: list[Path] = []
    monkeypatch.setattr(
        create_snapshot_module,
        "stamp_alembic_head_for_sqlite_path",
        lambda path: stamped_paths.append(path),
    )

    def fake_run_schema_seed_and_stamp(
        *,
        engine,
        metadata,
        make_session,
        seed,
        recreate_schema,
        stamp,
    ):
        db_path = snap_dir / "db.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(b"sqlite-bytes")
        stamp()
        return seed(None)

    monkeypatch.setattr(
        create_snapshot_module,
        "run_schema_seed_and_stamp",
        fake_run_schema_seed_and_stamp,
    )

    result = create_snapshot_module.create_default_snapshot()
    metadata = json.loads((snap_dir / "metadata.json").read_text(encoding="utf-8"))
    assert result.user_name == "admin"
    assert result.account_names == ["Scotiabank Debit", "Scotiabank Credit"]
    assert result.has_user_memory is True
    assert metadata["name"] == "default"
    assert stamped_paths == [snap_dir / "db.sqlite3"]


def test_check_docs_sync_reports_latest_migration_file():
    from scripts import check_docs_sync

    latest = check_docs_sync.get_latest_migration_filename()
    assert latest.endswith(".py")
    assert latest[:4].isdigit()


def test_seed_defaults_tag_color_is_stable():
    from scripts import seed_defaults

    first = seed_defaults._tag_color("coffee_snacks")
    second = seed_defaults._tag_color("coffee_snacks")
    assert first == second
    assert first.startswith("hsl(")


def test_seed_defaults_seed_accounts_uses_entity_root_account_ids(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import backend.models_finance  # noqa: F401
    from backend.db_meta import Base
    from scripts import seed_defaults

    engine = create_engine(f"sqlite:///{tmp_path / 'seed-defaults.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    with SessionLocal() as db:
        user, debit, credit = seed_defaults.seed_accounts(db)
        assert debit.id == debit.entity.id
        assert credit.id == credit.entity.id
        assert debit.owner_user_id == user.id
        assert credit.owner_user_id == user.id


def test_seed_demo_parsers_and_location_detection():
    from backend.enums_finance import EntryKind
    from scripts import seed_demo

    assert seed_demo._parse_amount_minor("12.34") == 1234
    assert seed_demo._parse_kind("credit") == EntryKind.INCOME
    assert seed_demo._parse_kind("debit") == EntryKind.EXPENSE
    assert seed_demo._extract_location_name("Toronto ON (Store #12)") == "toronto on"

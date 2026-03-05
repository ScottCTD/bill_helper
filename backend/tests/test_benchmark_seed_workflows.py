from __future__ import annotations

import csv
from pathlib import Path

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.database import get_session_maker
from benchmark import runner, scorer
from scripts import seed_defaults, seed_demo


def test_runner_create_isolated_db_requires_snapshot(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "SNAPSHOTS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        runner._create_isolated_db("missing_snapshot")


def test_scorer_score_case_requires_results_file(monkeypatch, tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    results_dir = tmp_path / "runs"
    case_dir = cases_dir / "case_001"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "ground_truth.json").write_text('{"tags":[],"entities":[],"entries":[]}')

    monkeypatch.setattr(scorer, "CASES_DIR", cases_dir)
    monkeypatch.setattr(scorer, "RESULTS_DIR", results_dir)

    with pytest.raises(FileNotFoundError):
        scorer.score_case("case_001", "run_missing")


def test_seed_demo_iter_credit_rows_skips_incomplete_lines(tmp_path: Path) -> None:
    csv_path = tmp_path / "credit.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Date", "Description", "Sub-description", "Type of Transaction", "Amount"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "Date": "2026-01-01",
                "Description": "Coffee Shop",
                "Sub-description": "",
                "Type of Transaction": "Debit",
                "Amount": "4.50",
            }
        )
        writer.writerow(
            {
                "Date": "",
                "Description": "Missing date should be ignored",
                "Sub-description": "",
                "Type of Transaction": "Debit",
                "Amount": "3.00",
            }
        )

    rows = seed_demo._iter_credit_rows(str(csv_path))
    assert len(rows) == 1
    assert rows[0]["Description"] == "Coffee Shop"


def test_seed_user_memory_best_effort_on_query_failure(monkeypatch, tmp_path: Path) -> None:
    prod_db_path = tmp_path / "bill_helper.db"
    prod_db_path.write_text("placeholder")

    class _FakeSettings:
        data_dir = tmp_path

    monkeypatch.setattr("backend.config.get_settings", lambda: _FakeSettings())

    class _FailingSession:
        def scalar(self, *_args, **_kwargs):
            raise SQLAlchemyError("boom")

        def close(self) -> None:
            return None

    class _Engine:
        def dispose(self) -> None:
            return None

    monkeypatch.setattr(seed_defaults, "build_engine_for_url", lambda *_args, **_kwargs: _Engine())
    monkeypatch.setattr(seed_defaults, "build_session_maker", lambda *args, **kwargs: (lambda: _FailingSession()))

    make_session = get_session_maker()
    db = make_session()
    try:
        result = seed_defaults.seed_user_memory(db, on_error="best_effort")
    finally:
        db.close()

    assert result is None


def test_seed_user_memory_fail_fast_on_query_failure(monkeypatch, tmp_path: Path) -> None:
    prod_db_path = tmp_path / "bill_helper.db"
    prod_db_path.write_text("placeholder")

    class _FakeSettings:
        data_dir = tmp_path

    monkeypatch.setattr("backend.config.get_settings", lambda: _FakeSettings())

    class _FailingSession:
        def scalar(self, *_args, **_kwargs):
            raise SQLAlchemyError("boom")

        def close(self) -> None:
            return None

    class _Engine:
        def dispose(self) -> None:
            return None

    monkeypatch.setattr(seed_defaults, "build_engine_for_url", lambda *_args, **_kwargs: _Engine())
    monkeypatch.setattr(seed_defaults, "build_session_maker", lambda *args, **kwargs: (lambda: _FailingSession()))

    make_session = get_session_maker()
    db = make_session()
    try:
        with pytest.raises(RuntimeError):
            seed_defaults.seed_user_memory(db, on_error="fail_fast")
    finally:
        db.close()

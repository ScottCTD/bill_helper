from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "benchmark" / "fixtures"
CASES_DIR = FIXTURES_DIR / "cases"
SNAPSHOTS_DIR = FIXTURES_DIR / "snapshots"
RESULTS_DIR = REPO_ROOT / "benchmark" / "results" / "runs"
REPORTS_DIR = REPO_ROOT / "benchmark" / "reports"

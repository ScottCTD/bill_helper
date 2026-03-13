# CALLING SPEC:
# - Purpose: provide benchmark support for `paths`.
# - Inputs: callers that import `benchmark/paths.py` and pass module-defined arguments or framework events.
# - Outputs: benchmark helpers, contracts, or entrypoints for `paths`.
# - Side effects: benchmark data loading, execution, or reporting as implemented below.
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "benchmark" / "fixtures"
CASES_DIR = FIXTURES_DIR / "cases"
SNAPSHOTS_DIR = FIXTURES_DIR / "snapshots"
RESULTS_DIR = REPO_ROOT / "benchmark" / "results" / "runs"
REPORTS_DIR = REPO_ROOT / "benchmark" / "reports"

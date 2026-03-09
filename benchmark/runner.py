"""Benchmark runner: execute cases against a model and capture results + traces.

Usage:
    uv run python -m benchmark.runner --model "openrouter/anthropic/claude-sonnet-4" --all-cases
    uv run python -m benchmark.runner --model "..." --cases case_001 case_002 --workers 4
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.database import build_engine_for_url, build_session_maker
from backend.schemas_settings import RuntimeSettingsUpdate
from backend.services.agent.benchmark_interface import (
    BenchmarkAttachmentInput,
    BenchmarkCaseExecution,
    run_benchmark_case,
)
from benchmark.io_utils import atomic_write_json
from benchmark.paths import CASES_DIR, REPO_ROOT, RESULTS_DIR, SNAPSHOTS_DIR
from backend.services.runtime_settings import update_runtime_settings_override
from benchmark.schemas import (
    CaseInput,
    CaseResult,
    PredictedEntity,
    PredictedEntry,
    PredictedTag,
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _model_slug(model_name: str) -> str:
    parts = model_name.strip().split("/")
    if len(parts) > 1:
        parts = parts[1:]
    return "--".join(parts).replace(" ", "_")


def _git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def _generate_run_id(model_name: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{ts}_{_model_slug(model_name)}"


def _create_isolated_db(snapshot_name: str) -> tuple[Path, Any, Any]:
    """Copy snapshot to temp file, return (temp_path, engine, SessionLocal)."""
    snapshot_db = SNAPSHOTS_DIR / snapshot_name / "db.sqlite3"
    if not snapshot_db.exists():
        raise FileNotFoundError(f"Snapshot DB not found: {snapshot_db}")

    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    tmp.close()
    tmp_path = Path(tmp.name)
    shutil.copy2(snapshot_db, tmp_path)

    eng = build_engine_for_url(f"sqlite:///{tmp_path}")
    session_factory = build_session_maker(eng)
    return tmp_path, eng, session_factory


@dataclass(slots=True)
class CaseContext:
    case_id: str
    case_dir: Path
    input_data: CaseInput
    attachments: list[BenchmarkAttachmentInput]


@dataclass(slots=True)
class CasePredictionBundle:
    case_result: CaseResult
    tags_count: int
    entities_count: int
    entries_count: int


@dataclass(slots=True)
class CaseSummary:
    case_id: str
    status: str
    tags_count: int
    entities_count: int
    entries_count: int
    wall_clock_ms: int
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "tags_count": self.tags_count,
            "entities_count": self.entities_count,
            "entries_count": self.entries_count,
            "wall_clock_ms": self.wall_clock_ms,
            "error": self.error,
        }


def _build_attachment_inputs(case_dir: Path, rel_paths: list[str]) -> list[BenchmarkAttachmentInput]:
    attachments: list[BenchmarkAttachmentInput] = []
    for rel_path in rel_paths:
        abs_path = str(case_dir / rel_path)
        suffix = Path(rel_path).suffix.lower()
        mime = "application/pdf" if suffix == ".pdf" else f"image/{suffix.lstrip('.')}"
        attachments.append(
            BenchmarkAttachmentInput(
                file_path=abs_path,
                mime_type=mime,
            )
        )
    return attachments


def _prepare_case_context(case_id: str) -> CaseContext:
    case_dir = CASES_DIR / case_id
    input_data = CaseInput.model_validate_json((case_dir / "input.json").read_text())
    attachments = _build_attachment_inputs(case_dir, input_data.attachment_paths)
    return CaseContext(
        case_id=case_id,
        case_dir=case_dir,
        input_data=input_data,
        attachments=attachments,
    )


def _close_case_resources(
    *,
    db: Session | None,
    engine: Any,
    temp_path: Path,
) -> None:
    def _log_cleanup_failure(stage: str, error: Exception) -> None:
        logger.warning(
            "benchmark cleanup step failed",
            extra={"stage": stage, "error_type": type(error).__name__, "error": str(error)},
        )

    if db is not None:
        try:
            db.close()
        except Exception as exc:
            _log_cleanup_failure("session_close", exc)
    try:
        engine.dispose()
    except Exception as exc:
        _log_cleanup_failure("engine_dispose", exc)
    try:
        temp_path.unlink(missing_ok=True)
    except Exception as exc:
        _log_cleanup_failure("tempfile_unlink", exc)


@contextmanager
def _isolated_case_session(snapshot_name: str) -> Iterator[Session]:
    temp_path, engine, make_session = _create_isolated_db(snapshot_name)
    db: Session | None = None
    try:
        db = make_session()
        yield db
    finally:
        _close_case_resources(
            db=db,
            engine=engine,
            temp_path=temp_path,
        )


def _run_case_execution(
    db: Session,
    *,
    model_name: str,
    context: CaseContext,
) -> BenchmarkCaseExecution:
    update_runtime_settings_override(
        db,
        RuntimeSettingsUpdate(agent_model=model_name),
    )
    db.commit()
    return run_benchmark_case(
        db,
        text=context.input_data.text,
        attachments=context.attachments,
    )


def _build_case_predictions(
    *,
    case_id: str,
    model_name: str,
    execution: BenchmarkCaseExecution,
) -> CasePredictionBundle:
    predicted_tags = [
        PredictedTag(
            name=item.get("name"),
            type=item.get("type"),
        )
        for item in execution.predictions.tags
    ]
    predicted_entities = [
        PredictedEntity(
            name=item.get("name"),
            category=item.get("category"),
        )
        for item in execution.predictions.entities
    ]
    predicted_entries = [
        PredictedEntry(
            kind=item.get("kind"),
            date=item.get("date"),
            name=item.get("name"),
            amount_minor=item.get("amount_minor"),
            currency_code=item.get("currency_code"),
            from_entity=item.get("from_entity"),
            to_entity=item.get("to_entity"),
            tags=item.get("tags", []),
            markdown_notes=item.get("markdown_notes") or item.get("markdown_body"),
        )
        for item in execution.predictions.entries
    ]
    return CasePredictionBundle(
        case_result=CaseResult(
            case_id=case_id,
            model=model_name,
            tags=predicted_tags,
            entities=predicted_entities,
            entries=predicted_entries,
            run_status=execution.run_status,
            error=execution.error,
        ),
        tags_count=len(predicted_tags),
        entities_count=len(predicted_entities),
        entries_count=len(predicted_entries),
    )


def _persist_case_outputs(
    *,
    run_id: str,
    case_id: str,
    model_name: str,
    case_result: CaseResult,
    execution: BenchmarkCaseExecution,
) -> None:
    out_dir = RESULTS_DIR / run_id / "cases" / case_id
    out_dir.mkdir(parents=True, exist_ok=True)

    atomic_write_json(
        out_dir / "results.json",
        case_result.model_dump(),
        default=str,
    )

    trace_dict = {
        "case_id": case_id,
        "model": model_name,
        "steps": [
            {
                "step": step.step,
                "messages_sent": step.messages_sent,
                "model_response": step.model_response,
                "tool_results": step.tool_results,
                "wall_clock_ms": step.wall_clock_ms,
            }
            for step in execution.trace_steps
        ],
        "total_usage": execution.total_usage,
        "total_wall_clock_ms": execution.total_wall_clock_ms,
        "final_assistant_content": execution.final_assistant_content,
        "error": execution.error,
    }
    atomic_write_json(
        out_dir / "trace.json",
        trace_dict,
        default=str,
    )


def _build_case_summary(
    *,
    case_id: str,
    execution: BenchmarkCaseExecution,
    predictions: CasePredictionBundle,
) -> CaseSummary:
    return CaseSummary(
        case_id=case_id,
        status=execution.run_status,
        tags_count=predictions.tags_count,
        entities_count=predictions.entities_count,
        entries_count=predictions.entries_count,
        wall_clock_ms=execution.total_wall_clock_ms,
        error=execution.error,
    )


def _format_case_summary(summary: dict[str, Any]) -> str:
    return (
        f"{summary['status']} "
        f"({summary['tags_count']} tags, "
        f"{summary['entities_count']} entities, "
        f"{summary['entries_count']} entries, "
        f"{summary['wall_clock_ms']}ms)"
    )


def _exception_case_summary(case_id: str, error: Exception) -> dict[str, Any]:
    return CaseSummary(
        case_id=case_id,
        status="exception",
        tags_count=0,
        entities_count=0,
        entries_count=0,
        wall_clock_ms=0,
        error=str(error),
    ).as_dict()


def run_single_case(
    case_id: str,
    model_name: str,
    run_id: str,
) -> dict[str, Any]:
    """Execute one benchmark case. Designed to run in a worker process."""
    context = _prepare_case_context(case_id)
    with _isolated_case_session(context.input_data.snapshot) as db:
        execution = _run_case_execution(db, model_name=model_name, context=context)
        predictions = _build_case_predictions(
            case_id=case_id,
            model_name=model_name,
            execution=execution,
        )
        _persist_case_outputs(
            run_id=run_id,
            case_id=case_id,
            model_name=model_name,
            case_result=predictions.case_result,
            execution=execution,
        )
    return _build_case_summary(
        case_id=case_id,
        execution=execution,
        predictions=predictions,
    ).as_dict()


def run_benchmark(
    model_name: str,
    case_ids: list[str],
    workers: int = 1,
) -> str:
    """Run benchmark for all specified cases. Returns the run_id."""
    run_id = _generate_run_id(model_name)
    run_dir = RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now_iso()
    print(f"Benchmark run: {run_id}")
    print(f"Model: {model_name}")
    print(f"Cases: {', '.join(case_ids)}")
    print(f"Workers: {workers}")
    print()

    summaries = []

    if workers <= 1:
        for cid in case_ids:
            print(f"  Running {cid}...", end=" ", flush=True)
            summary = run_single_case(cid, model_name, run_id)
            summaries.append(summary)
            print(_format_case_summary(summary))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(run_single_case, cid, model_name, run_id): cid
                for cid in case_ids
            }
            for future in as_completed(futures):
                cid = futures[future]
                try:
                    summary = future.result()
                    summaries.append(summary)
                    print(f"  {cid}: {_format_case_summary(summary)}")
                except Exception as exc:
                    print(f"  {cid}: EXCEPTION -- {exc}")
                    summaries.append(_exception_case_summary(cid, exc))

    completed_at = _utc_now_iso()

    meta = {
        "run_id": run_id,
        "model": model_name,
        "cases": case_ids,
        "started_at": started_at,
        "completed_at": completed_at,
        "git_sha": _git_sha(),
        "workers": workers,
        "summaries": summaries,
    }
    atomic_write_json(run_dir / "run_meta.json", meta)

    print()
    print(f"Run complete: {run_id}")
    print(f"Results: {run_dir}")
    return run_id


def _discover_cases() -> list[str]:
    if not CASES_DIR.exists():
        return []
    return sorted(
        d.name for d in CASES_DIR.iterdir()
        if d.is_dir() and (d / "input.json").exists()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run benchmark cases against a model.")
    parser.add_argument("--model", required=True, help="LiteLLM model identifier")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cases", nargs="+", help="Case IDs to run")
    group.add_argument("--all-cases", action="store_true", help="Run all discovered cases")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers (default: 1)")

    args = parser.parse_args()

    try:
        if args.all_cases:
            case_ids = _discover_cases()
            if not case_ids:
                raise FileNotFoundError("no cases found under benchmark/fixtures/cases/")
        else:
            case_ids = args.cases

        for cid in case_ids:
            if not (CASES_DIR / cid / "input.json").exists():
                raise FileNotFoundError(
                    f"case '{cid}' not found (missing input.json)"
                )

        run_benchmark(args.model, case_ids, workers=args.workers)
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

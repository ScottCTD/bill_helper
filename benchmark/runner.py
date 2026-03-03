"""Benchmark runner: execute cases against a model and capture results + traces.

Usage:
    uv run python -m benchmark.runner --model "openrouter/anthropic/claude-sonnet-4" --all-cases
    uv run python -m benchmark.runner --model "..." --cases case_001 case_002 --workers 4
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "benchmark" / "fixtures"
CASES_DIR = FIXTURES_DIR / "cases"
SNAPSHOTS_DIR = FIXTURES_DIR / "snapshots"
RESULTS_DIR = REPO_ROOT / "benchmark" / "results" / "runs"


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


@dataclass
class TraceStep:
    step: int
    messages_sent: list[dict[str, Any]]
    model_response: dict[str, Any]
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    wall_clock_ms: int = 0


@dataclass
class CaseTrace:
    case_id: str
    model: str
    steps: list[TraceStep] = field(default_factory=list)
    total_usage: dict[str, int | None] = field(default_factory=dict)
    total_wall_clock_ms: int = 0
    final_assistant_content: str = ""
    error: str | None = None


def _create_isolated_db(snapshot_name: str) -> tuple[Path, Any, Any]:
    """Copy snapshot to temp file, return (temp_path, engine, SessionLocal)."""
    snapshot_db = SNAPSHOTS_DIR / snapshot_name / "db.sqlite3"
    if not snapshot_db.exists():
        raise FileNotFoundError(f"Snapshot DB not found: {snapshot_db}")

    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    tmp.close()
    tmp_path = Path(tmp.name)
    shutil.copy2(snapshot_db, tmp_path)

    eng = create_engine(
        f"sqlite:///{tmp_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=eng, autocommit=False, autoflush=False, class_=Session)
    return tmp_path, eng, session_factory


def _redact_image_content(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace base64 image data with a placeholder for trace storage."""
    redacted = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            new_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    url = (part.get("image_url") or {}).get("url", "")
                    if url.startswith("data:"):
                        media_type = url.split(";")[0] if ";" in url else "data:image/unknown"
                        new_parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"{media_type};base64,[REDACTED {len(url)} chars]"},
                        })
                    else:
                        new_parts.append(part)
                else:
                    new_parts.append(part)
            redacted.append({**msg, "content": new_parts})
        else:
            redacted.append(msg)
    return redacted


def _accumulate_usage(totals: dict[str, int | None], usage: dict[str, int | None]) -> None:
    for key, value in usage.items():
        if value is None:
            continue
        current = totals.get(key)
        totals[key] = value if current is None else current + value


def _extract_usage(response: dict[str, Any]) -> dict[str, int | None]:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return {}
    fields = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
    result = {}
    for f in fields:
        v = usage.get(f)
        result[f] = v if isinstance(v, int) else None
    return result


def _parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return {}
    try:
        return dict(raw)
    except (TypeError, ValueError):
        return {}


def run_single_case(
    case_id: str,
    model_name: str,
    run_id: str,
) -> dict[str, Any]:
    """Execute one benchmark case. Designed to run in a worker process."""
    # Late imports to avoid polluting the main process and to ensure each worker
    # gets its own module state.
    from backend.enums import AgentMessageRole, AgentRunStatus, AgentToolCallStatus
    from backend.models import (
        AgentMessage,
        AgentMessageAttachment,
        AgentRun,
        AgentThread,
        AgentToolCall,
    )
    from backend.services.agent.message_history import build_llm_messages
    from backend.services.agent.model_client import AgentModelError, LiteLLMModelClient
    from backend.services.agent.tools import (
        ToolContext,
        build_openai_tool_schemas,
        execute_tool,
    )
    from backend.services.runtime_settings import (
        resolve_runtime_settings,
        update_runtime_settings_override,
    )

    from benchmark.schemas import CaseInput, CaseResult, PredictedEntity, PredictedEntry, PredictedTag

    case_dir = CASES_DIR / case_id
    input_data = CaseInput.model_validate_json((case_dir / "input.json").read_text())

    tmp_path, eng, make_session = _create_isolated_db(input_data.snapshot)

    try:
        db: Session = make_session()

        update_runtime_settings_override(db, {"agent_model": model_name})
        db.commit()

        settings = resolve_runtime_settings(db)

        thread = AgentThread()
        db.add(thread)
        db.flush()

        user_msg = AgentMessage(
            thread_id=thread.id,
            role=AgentMessageRole.USER,
            content_markdown=input_data.text,
        )
        db.add(user_msg)
        db.flush()

        for rel_path in input_data.attachment_paths:
            abs_path = str(case_dir / rel_path)
            suffix = Path(rel_path).suffix.lower()
            mime = "application/pdf" if suffix == ".pdf" else f"image/{suffix.lstrip('.')}"
            attachment = AgentMessageAttachment(
                message_id=user_msg.id,
                mime_type=mime,
                file_path=abs_path,
            )
            db.add(attachment)
        db.flush()

        run = AgentRun(
            thread_id=thread.id,
            user_message_id=user_msg.id,
            status=AgentRunStatus.RUNNING,
            model_name=model_name,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        tool_schemas = build_openai_tool_schemas()
        model_client = LiteLLMModelClient(
            model_name=settings.agent_model,
            tools=tool_schemas,
            retry_max_attempts=settings.agent_retry_max_attempts,
            retry_initial_wait_seconds=settings.agent_retry_initial_wait_seconds,
            retry_max_wait_seconds=settings.agent_retry_max_wait_seconds,
            retry_backoff_multiplier=settings.agent_retry_backoff_multiplier,
        )

        llm_messages = build_llm_messages(db, thread.id, current_user_message_id=user_msg.id)
        tool_context = ToolContext(db=db, run_id=run.id)
        max_steps = max(settings.agent_max_steps, 1)

        trace = CaseTrace(case_id=case_id, model=model_name)
        usage_totals: dict[str, int | None] = {}
        overall_start = time.monotonic()

        try:
            for step_idx in range(max_steps):
                step_start = time.monotonic()

                messages_snapshot = _redact_image_content(llm_messages)

                assistant_msg = model_client.complete(llm_messages)

                step_usage = _extract_usage(assistant_msg)
                _accumulate_usage(usage_totals, step_usage)

                tool_calls = assistant_msg.get("tool_calls") or []
                assistant_content = assistant_msg.get("content") or ""

                trace_step = TraceStep(
                    step=step_idx + 1,
                    messages_sent=messages_snapshot,
                    model_response={
                        "content": assistant_content,
                        "tool_calls": tool_calls,
                        "usage": step_usage,
                    },
                )

                if tool_calls:
                    llm_messages.append({
                        "role": "assistant",
                        "content": assistant_content,
                        "tool_calls": tool_calls,
                    })

                    for tc in tool_calls:
                        func = tc.get("function") or {}
                        name = str(func.get("name") or "")
                        arguments = _parse_tool_arguments(func.get("arguments") or "{}")

                        result = execute_tool(name, arguments, tool_context)

                        tool_row = AgentToolCall(
                            run_id=run.id,
                            tool_name=name or "(unknown)",
                            input_json=arguments,
                            output_json=result.output_json,
                            output_text=result.output_text,
                            status=AgentToolCallStatus.OK if result.status == "ok" else AgentToolCallStatus.ERROR,
                        )
                        db.add(tool_row)
                        db.flush()

                        tool_msg = {
                            "role": "tool",
                            "tool_call_id": tc.get("id"),
                            "name": name,
                            "content": result.output_text,
                        }
                        llm_messages.append(tool_msg)

                        trace_step.tool_results.append({
                            "tool_name": name,
                            "input": arguments,
                            "output": result.output_json,
                            "status": result.status,
                        })
                    db.commit()

                    trace_step.wall_clock_ms = int((time.monotonic() - step_start) * 1000)
                    trace.steps.append(trace_step)
                    continue

                trace_step.wall_clock_ms = int((time.monotonic() - step_start) * 1000)
                trace.steps.append(trace_step)
                trace.final_assistant_content = assistant_content

                run.status = AgentRunStatus.COMPLETED
                db.add(run)
                db.commit()
                break
            else:
                run.status = AgentRunStatus.FAILED
                run.error_text = "maximum tool steps reached"
                db.add(run)
                db.commit()
                trace.error = "maximum tool steps reached"

        except AgentModelError as exc:
            run.status = AgentRunStatus.FAILED
            run.error_text = str(exc)
            db.add(run)
            db.commit()
            trace.error = str(exc)
        except Exception as exc:
            run.status = AgentRunStatus.FAILED
            run.error_text = str(exc)
            db.add(run)
            db.commit()
            trace.error = str(exc)

        trace.total_wall_clock_ms = int((time.monotonic() - overall_start) * 1000)
        trace.total_usage = usage_totals

        all_tool_calls = list(
            db.scalars(
                select(AgentToolCall)
                .where(AgentToolCall.run_id == run.id)
                .order_by(AgentToolCall.created_at.asc())
            )
        )

        predicted_tags: list[PredictedTag] = []
        predicted_entities: list[PredictedEntity] = []
        predicted: list[PredictedEntry] = []

        for tc in all_tool_calls:
            inp = tc.input_json if isinstance(tc.input_json, dict) else {}
            if tc.tool_name == "propose_create_tag":
                predicted_tags.append(PredictedTag(
                    name=inp.get("name"),
                    category=inp.get("category"),
                ))
            elif tc.tool_name == "propose_create_entity":
                predicted_entities.append(PredictedEntity(
                    name=inp.get("name"),
                    category=inp.get("category"),
                ))
            elif tc.tool_name == "propose_create_entry":
                predicted.append(PredictedEntry(
                    kind=inp.get("kind"),
                    date=inp.get("date"),
                    name=inp.get("name"),
                    amount_minor=inp.get("amount_minor"),
                    currency_code=inp.get("currency_code"),
                    from_entity=inp.get("from_entity"),
                    to_entity=inp.get("to_entity"),
                    tags=inp.get("tags", []),
                    markdown_notes=inp.get("markdown_notes"),
                ))

        case_result = CaseResult(
            case_id=case_id,
            model=model_name,
            tags=predicted_tags,
            entities=predicted_entities,
            entries=predicted,
            run_status=run.status.value,
            error=run.error_text,
        )

        db.close()
        eng.dispose()

        out_dir = RESULTS_DIR / run_id / "cases" / case_id
        out_dir.mkdir(parents=True, exist_ok=True)

        (out_dir / "results.json").write_text(
            json.dumps(case_result.model_dump(), indent=2, default=str) + "\n"
        )

        trace_dict = {
            "case_id": trace.case_id,
            "model": trace.model,
            "steps": [
                {
                    "step": s.step,
                    "messages_sent": s.messages_sent,
                    "model_response": s.model_response,
                    "tool_results": s.tool_results,
                    "wall_clock_ms": s.wall_clock_ms,
                }
                for s in trace.steps
            ],
            "total_usage": trace.total_usage,
            "total_wall_clock_ms": trace.total_wall_clock_ms,
            "final_assistant_content": trace.final_assistant_content,
            "error": trace.error,
        }
        (out_dir / "trace.json").write_text(
            json.dumps(trace_dict, indent=2, default=str) + "\n"
        )

        return {
            "case_id": case_id,
            "status": run.status.value,
            "tags_count": len(predicted_tags),
            "entities_count": len(predicted_entities),
            "entries_count": len(predicted),
            "wall_clock_ms": trace.total_wall_clock_ms,
            "error": trace.error,
        }

    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


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
            status = summary["status"]
            t = summary["tags_count"]
            e = summary["entities_count"]
            n = summary["entries_count"]
            ms = summary["wall_clock_ms"]
            print(f"{status} ({t} tags, {e} entities, {n} entries, {ms}ms)")
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
                    status = summary["status"]
                    t = summary["tags_count"]
                    e = summary["entities_count"]
                    n = summary["entries_count"]
                    ms = summary["wall_clock_ms"]
                    print(f"  {cid}: {status} ({t} tags, {e} entities, {n} entries, {ms}ms)")
                except Exception as exc:
                    print(f"  {cid}: EXCEPTION -- {exc}")
                    summaries.append({
                        "case_id": cid,
                        "status": "exception",
                        "entries_count": 0,
                        "wall_clock_ms": 0,
                        "error": str(exc),
                    })

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
    (run_dir / "run_meta.json").write_text(json.dumps(meta, indent=2) + "\n")

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmark cases against a model.")
    parser.add_argument("--model", required=True, help="LiteLLM model identifier")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cases", nargs="+", help="Case IDs to run")
    group.add_argument("--all-cases", action="store_true", help="Run all discovered cases")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers (default: 1)")

    args = parser.parse_args()

    if args.all_cases:
        case_ids = _discover_cases()
        if not case_ids:
            print("No cases found under benchmark/fixtures/cases/", file=sys.stderr)
            sys.exit(1)
    else:
        case_ids = args.cases

    for cid in case_ids:
        if not (CASES_DIR / cid / "input.json").exists():
            print(f"Error: case '{cid}' not found (missing input.json)", file=sys.stderr)
            sys.exit(1)

    run_benchmark(args.model, case_ids, workers=args.workers)


if __name__ == "__main__":
    main()

"""Terminal execution for agent runs.

CALLING SPEC:
    run_terminal(context, args) -> ToolExecutionResult

Inputs:
    - current tool context with run/principal scope
    - command string, optional cwd, timeout
Outputs:
    - structured command result with exit code, stdout, stderr, cwd, and truncation flags
Side effects:
    - ensures the user's workspace container is running, mints a short-lived backend session token,
      executes a shell command inside the workspace container, and revokes the temporary session
"""

from __future__ import annotations

from datetime import timedelta
import logging
from time import monotonic
from typing import Any

from sqlalchemy import select

from backend.config import get_settings
from backend.database import open_session
from backend.models_agent import AgentRun
from backend.models_finance import User
from backend.services import docker_cli
from backend.services.agent.tool_args.terminal import RunTerminalArgs
from backend.services.agent.tool_results import format_lines
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus
from backend.services.agent_workspace import start_user_workspace
from backend.services.sessions import create_session, revoke_session_by_id, utc_now

_DEFAULT_WORKSPACE_ROOT = "/workspace/workspace"
_DEFAULT_DATA_ROOT = "/workspace/user_data"
_MAX_OUTPUT_CHARS = 12000
logger = logging.getLogger(__name__)


def run_terminal(context: ToolContext, args: RunTerminalArgs) -> ToolExecutionResult:
    try:
        execution = _execute_terminal(context, args=args)
    except (docker_cli.DockerCliError, ValueError) as exc:
        return ToolExecutionResult(
            output_text=format_lines(
                [
                    "ERROR",
                    "summary: terminal command failed",
                    f"details: {exc}",
                ]
            ),
            output_json={
                "summary": "terminal command failed",
                "details": str(exc),
            },
            status=ToolExecutionStatus.ERROR,
        )
    except Exception as exc:  # pragma: no cover - guarded runtime fallback
        logger.exception(
            "Terminal tool failed unexpectedly: scope=agent_terminal run_id=%s user_id=%s cwd=%s command=%s error_type=%s",
            context.run_id,
            context.principal_user_id,
            args.cwd or _DEFAULT_WORKSPACE_ROOT,
            args.command,
            type(exc).__name__,
        )
        return ToolExecutionResult(
            output_text=format_lines(
                [
                    "ERROR",
                    "summary: terminal command failed",
                    f"details: {exc}",
                ]
            ),
            output_json={
                "summary": "terminal command failed",
                "details": str(exc),
            },
            status=ToolExecutionStatus.ERROR,
        )
    return ToolExecutionResult(
        output_text=format_lines(_result_lines(execution)),
        output_json=execution,
        status=ToolExecutionStatus.OK if execution["exit_code"] == 0 else ToolExecutionStatus.ERROR,
    )


def _execute_terminal(context: ToolContext, *, args: RunTerminalArgs) -> dict[str, Any]:
    principal_user_id = (context.principal_user_id or "").strip()
    if not principal_user_id:
        raise ValueError("Terminal tool requires a principal user.")
    thread_id = _thread_id_for_run(context)
    settings = get_settings()
    spec = start_user_workspace(user_id=principal_user_id, settings=settings)
    session_token, session_id = _create_temporary_session(user_id=principal_user_id)
    env = {
        "BH_API_BASE_URL": settings.workspace_backend_base_url,
        "BH_AUTH_TOKEN": session_token,
        "BH_THREAD_ID": thread_id,
        "BH_RUN_ID": context.run_id,
        "BH_WORKSPACE_ROOT": _DEFAULT_WORKSPACE_ROOT,
        "BH_DATA_ROOT": _DEFAULT_DATA_ROOT,
    }
    command_cwd = args.cwd or _DEFAULT_WORKSPACE_ROOT
    started_at = monotonic()
    try:
        completed = docker_cli.exec_in_container(
            docker_binary=spec.docker_binary,
            container_name=spec.container_name,
            command=["bash", "-lc", args.command],
            env=env,
            workdir=command_cwd,
            timeout_seconds=float(args.timeout_seconds),
        )
        raw_stdout = completed.stdout or ""
        raw_stderr = completed.stderr or ""
        exit_code = int(completed.returncode)
    except docker_cli.DockerCliError as error:
        raw_stdout = error.stdout or ""
        raw_stderr = error.stderr or ""
        exit_code = int(error.exit_code)
    finally:
        _revoke_temporary_session(session_id=session_id)
    duration_ms = int((monotonic() - started_at) * 1000)
    stdout, stdout_truncated = _truncate_and_scrub(raw_stdout, secret=session_token)
    stderr, stderr_truncated = _truncate_and_scrub(raw_stderr, secret=session_token)
    return {
        "summary": "terminal command completed" if exit_code == 0 else "terminal command exited non-zero",
        "command": args.command,
        "cwd": command_cwd,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "duration_ms": duration_ms,
    }


def _thread_id_for_run(context: ToolContext) -> str:
    thread_id = context.db.scalar(select(AgentRun.thread_id).where(AgentRun.id == context.run_id))
    if not isinstance(thread_id, str) or not thread_id:
        raise ValueError("Terminal tool requires a valid run/thread context.")
    return thread_id


def _create_temporary_session(*, user_id: str) -> tuple[str, str]:
    db = open_session()
    try:
        user = db.get(User, user_id)
        if user is None:
            raise ValueError("Terminal tool user not found.")
        expires_at = utc_now() + timedelta(minutes=10)
        token, session_row = create_session(
            db,
            user=user,
            expires_at=expires_at,
        )
        db.commit()
        return token, session_row.id
    finally:
        db.close()


def _revoke_temporary_session(*, session_id: str) -> None:
    db = open_session()
    try:
        revoke_session_by_id(db, session_id=session_id)
        db.commit()
    finally:
        db.close()


def _truncate_and_scrub(value: str, *, secret: str) -> tuple[str, bool]:
    scrubbed = value.replace(secret, "***") if secret else value
    if len(scrubbed) <= _MAX_OUTPUT_CHARS:
        return scrubbed, False
    return scrubbed[:_MAX_OUTPUT_CHARS], True


def _result_lines(payload: dict[str, Any]) -> list[str]:
    return [
        "OK" if payload["exit_code"] == 0 else "ERROR",
        f"summary: {payload['summary']}",
        f"exit_code: {payload['exit_code']}",
        f"cwd: {payload['cwd']}",
        f"duration_ms: {payload['duration_ms']}",
        f"stdout_truncated: {payload['stdout_truncated']}",
        f"stderr_truncated: {payload['stderr_truncated']}",
        f"stdout: {payload['stdout']}",
        f"stderr: {payload['stderr']}",
    ]

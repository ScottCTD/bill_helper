"""Shared support helpers for the `billengine` CLI.

CALLING SPEC:
    build_cli_context(output_format=None) -> CliContext
    request_json(context, method, path, params=None, json_body=None) -> tuple[int, object]
    print_output(payload, output_format=context.output_format) -> None
    load_json_argument(inline_json=..., json_file=...) -> object

Inputs:
    - environment-provided backend/auth/thread/run defaults and command-specific request data
Outputs:
    - a thin HTTP client context, decoded JSON payloads, and rendered CLI output
Side effects:
    - reads environment variables, performs HTTP requests, and writes stdout/stderr
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import sys
from typing import Any

import httpx


_RUN_ID_HEADER = "X-Bill-Helper-Agent-Run-Id"


@dataclass(frozen=True, slots=True)
class CliContext:
    api_base_url: str
    auth_token: str
    thread_id: str | None
    run_id: str | None
    output_format: str


class CliError(RuntimeError):
    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def build_cli_context(*, output_format: str | None = None) -> CliContext:
    api_base_url = _required_env("BILLENGINE_API_BASE_URL")
    auth_token = _required_env("BILLENGINE_AUTH_TOKEN")
    resolved_format = output_format or ("text" if sys.stdout.isatty() else "json")
    return CliContext(
        api_base_url=api_base_url.rstrip("/"),
        auth_token=auth_token,
        thread_id=_optional_env("BILLENGINE_THREAD_ID"),
        run_id=_optional_env("BILLENGINE_RUN_ID"),
        output_format=resolved_format,
    )


def request_json(
    context: CliContext,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    include_run_id: bool = False,
) -> tuple[int, Any]:
    headers = {"Authorization": f"Bearer {context.auth_token}"}
    if include_run_id:
        run_id = (context.run_id or "").strip()
        if not run_id:
            raise CliError("This command requires BILLENGINE_RUN_ID in the environment.")
        headers[_RUN_ID_HEADER] = run_id
    response = httpx.request(
        method,
        f"{context.api_base_url}{path}",
        headers=headers,
        params=_clean_mapping(params),
        json=json_body,
        timeout=30.0,
    )
    if response.status_code >= 400:
        try:
            payload = response.json()
        except ValueError:
            payload = {"detail": response.text or response.reason_phrase}
        detail = payload.get("detail", payload)
        raise CliError(
            json.dumps(
                {
                    "status": "ERROR",
                    "status_code": response.status_code,
                    "detail": detail,
                },
                indent=2,
            )
        )
    if response.status_code == 204 or not response.content:
        return response.status_code, {"status": "OK"}
    return response.status_code, response.json()


def resolve_thread_id(context: CliContext, *, override: str | None = None) -> str:
    candidate = (override or context.thread_id or "").strip()
    if not candidate:
        raise CliError("This command requires --thread or BILLENGINE_THREAD_ID.")
    return candidate


def resolve_proposal_id(context: CliContext, *, thread_id: str, proposal_id: str) -> str:
    _, payload = request_json(
        context,
        "GET",
        f"/agent/threads/{thread_id}/proposals/{proposal_id}",
        include_run_id=True,
    )
    if not isinstance(payload, dict) or "proposal_id" not in payload:
        raise CliError("Unable to resolve proposal id.")
    return str(payload["proposal_id"])


def load_json_argument(*, inline_json: str | None, json_file: str | None) -> Any:
    if bool(inline_json) == bool(json_file):
        raise CliError("Provide exactly one of the inline JSON or file JSON options.")
    if inline_json is not None:
        source = inline_json
    else:
        with open(json_file, encoding="utf-8") as handle:
            source = handle.read()
    try:
        return json.loads(source)
    except json.JSONDecodeError as exc:
        raise CliError(f"Invalid JSON input: {exc}") from exc


def print_output(payload: Any, *, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(str(payload))


def _required_env(name: str) -> str:
    value = _optional_env(name)
    if value is None:
        raise CliError(f"Missing required environment variable {name}.")
    return value


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    normalized = (value or "").strip()
    return normalized or None


def _clean_mapping(values: dict[str, Any] | None) -> dict[str, Any] | None:
    if values is None:
        return None
    return {key: value for key, value in values.items() if value is not None}

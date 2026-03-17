"""Shared support helpers for the `bh` CLI.

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
from pathlib import Path
import sys
from typing import Any
from collections.abc import Callable

import httpx

from backend.cli.rendering import render_output


_RUN_ID_HEADER = "X-Bill-Helper-Agent-Run-Id"
_WORKSPACE_CLI_CONFIG_PATH = Path("/workspace/.ide/bh-env.json")


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
    workspace_config = _load_workspace_cli_config()
    api_base_url = _required_value(
        env_names=("BH_API_BASE_URL",),
        workspace_config=workspace_config,
        config_key="api_base_url",
        error_message=(
            "Missing CLI API base URL. Set BH_API_BASE_URL "
            "or launch the workspace IDE so /workspace/.ide/bh-env.json is created."
        ),
    )
    auth_token = _required_value(
        env_names=("BH_AUTH_TOKEN",),
        workspace_config=workspace_config,
        config_key="auth_token",
        error_message=(
            "Missing CLI auth token. Set BH_AUTH_TOKEN "
            "or launch the workspace IDE so /workspace/.ide/bh-env.json is created."
        ),
    )
    resolved_format = output_format or ("text" if sys.stdout.isatty() else "compact")
    return CliContext(
        api_base_url=api_base_url.rstrip("/"),
        auth_token=auth_token,
        thread_id=_first_env(("BH_THREAD_ID",)),
        run_id=_first_env(("BH_RUN_ID",)),
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
    error_formatter: Callable[[int, Any], str] | None = None,
) -> tuple[int, Any]:
    headers = {"Authorization": f"Bearer {context.auth_token}"}
    if include_run_id:
        run_id = (context.run_id or "").strip()
        if not run_id:
            raise CliError("This command requires BH_RUN_ID in the environment.")
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
        if error_formatter is not None:
            raise CliError(error_formatter(response.status_code, detail))
        raise CliError(
            _default_error_message(status_code=response.status_code, detail=detail)
        )
    if response.status_code == 204 or not response.content:
        return response.status_code, {"status": "OK"}
    return response.status_code, response.json()


def resolve_thread_id(context: CliContext, *, override: str | None = None) -> str:
    candidate = (override or context.thread_id or "").strip()
    if not candidate:
        raise CliError("This command requires BH_THREAD_ID. Proposal commands are only available during agent runs.")
    return candidate


def resolve_entry_id(context: CliContext, *, entry_id: str) -> str:
    return _resolve_entry_id(context, entry_id=entry_id)


def resolve_account_id(context: CliContext, *, account_id: str) -> str:
    payload = _list_accounts(context)
    return _resolve_id_from_records(
        records=payload,
        candidate_id=account_id,
        resource_label="account",
    )


def resolve_account_name(context: CliContext, *, account_ref: str) -> str:
    records = _list_accounts(context)
    normalized = account_ref.strip().lower()
    if not normalized:
        raise CliError("Missing account reference.")
    exact_name_matches = [
        record
        for record in records
        if str(record.get("name") or "").strip().lower() == normalized
    ]
    if len(exact_name_matches) == 1:
        return str(exact_name_matches[0]["name"])
    if len(exact_name_matches) > 1:
        names = ", ".join(str(record.get("name")) for record in exact_name_matches[:5])
        raise CliError(f"Ambiguous account reference '{account_ref}'. Use one of: {names}")

    resolved_id = _resolve_id_from_records(
        records=records,
        candidate_id=account_ref,
        resource_label="account",
    )
    matched = next((record for record in records if str(record.get("id") or "") == resolved_id), None)
    if matched is None:
        raise CliError(f"Unable to resolve account reference '{account_ref}'.")
    return str(matched["name"])


def resolve_group_id(context: CliContext, *, group_id: str) -> str:
    _, payload = request_json(context, "GET", "/groups")
    return _resolve_id_from_records(
        records=payload if isinstance(payload, list) else [],
        candidate_id=group_id,
        resource_label="group",
    )


def resolve_proposal_id(context: CliContext, *, thread_id: str, proposal_id: str) -> str:
    normalized = proposal_id.strip()
    if not normalized:
        raise CliError("Missing proposal id.")
    _, payload = request_json(
        context,
        "GET",
        f"/agent/threads/{thread_id}/proposals",
        params={"limit": 5000},
        include_run_id=True,
    )
    records = payload.get("proposals") if isinstance(payload, dict) else []
    if not isinstance(records, list):
        records = []
    return _resolve_id_from_records(
        records=records,
        candidate_id=normalized,
        resource_label="proposal",
        id_field="proposal_id",
    )


def resolve_snapshot_id(context: CliContext, *, account_id: str, snapshot_id: str) -> str:
    normalized = snapshot_id.strip()
    if not normalized:
        raise CliError("Missing snapshot id.")
    _, payload = request_json(context, "GET", f"/accounts/{account_id}/snapshots")
    records = payload if isinstance(payload, list) else []
    return _resolve_id_from_records(
        records=records,
        candidate_id=normalized,
        resource_label="snapshot",
    )


def resolve_payload_proposal_references(context: CliContext, *, thread_id: str, payload: Any) -> Any:
    cache: dict[str, str] = {}
    records_state: dict[str, list[dict[str, Any]] | None] = {"records": None}
    return _resolve_payload_proposal_references(
        context,
        thread_id=thread_id,
        payload=payload,
        cache=cache,
        records_state=records_state,
    )


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


def print_output(payload: Any, *, output_format: str, render_key: str | None = None) -> None:
    print(render_output(payload, output_format=output_format, render_key=render_key))


def _required_value(
    *,
    env_names: tuple[str, ...],
    workspace_config: dict[str, Any],
    config_key: str,
    error_message: str,
) -> str:
    env_value = _first_env(env_names)
    if env_value is not None:
        return env_value
    config_value = workspace_config.get(config_key)
    if isinstance(config_value, str):
        normalized = config_value.strip()
        if normalized:
            return normalized
    raise CliError(error_message)


def _first_env(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = _optional_env(name)
        if value is not None:
            return value
    return None


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    normalized = (value or "").strip()
    return normalized or None


def _load_workspace_cli_config() -> dict[str, Any]:
    try:
        raw_text = _WORKSPACE_CLI_CONFIG_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise CliError(f"Failed to read {_WORKSPACE_CLI_CONFIG_PATH}: {exc}") from exc
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise CliError(f"Invalid workspace CLI config at {_WORKSPACE_CLI_CONFIG_PATH}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CliError(f"Invalid workspace CLI config at {_WORKSPACE_CLI_CONFIG_PATH}: expected object.")
    return payload


def _clean_mapping(values: dict[str, Any] | None) -> dict[str, Any] | None:
    if values is None:
        return None
    return {key: value for key, value in values.items() if value is not None}


def _default_error_message(*, status_code: int, detail: Any) -> str:
    return json.dumps(
        {
            "status": "ERROR",
            "status_code": status_code,
            "detail": detail,
        },
        indent=2,
    )


def _list_accounts(context: CliContext) -> list[dict[str, Any]]:
    _, payload = request_json(context, "GET", "/accounts")
    return payload if isinstance(payload, list) else []


def _resolve_entry_id(context: CliContext, *, entry_id: str) -> str:
    normalized = entry_id.strip()
    if not normalized:
        raise CliError("Missing entry id.")
    offset = 0
    limit = 200
    prefix_matches: list[dict[str, Any]] = []
    while offset < 5000:
        _, payload = request_json(
            context,
            "GET",
            "/entries",
            params={"limit": limit, "offset": offset},
        )
        if not isinstance(payload, dict):
            break
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            break
        for record in items:
            record_id = str(record.get("id") or "").strip()
            if record_id.lower() == normalized.lower():
                return record_id
            if record_id.lower().startswith(normalized.lower()):
                prefix_matches.append(record)
        if len(items) < limit:
            break
        offset += limit
    return _resolve_id_from_records(
        records=prefix_matches,
        candidate_id=normalized,
        resource_label="entry",
        allow_exact=False,
    )


def _resolve_id_from_records(
    *,
    records: list[dict[str, Any]],
    candidate_id: str,
    resource_label: str,
    allow_exact: bool = True,
    id_field: str = "id",
) -> str:
    normalized = candidate_id.strip().lower()
    if not normalized:
        raise CliError(f"Missing {resource_label} id.")
    if allow_exact:
        exact = [record for record in records if str(record.get(id_field) or "").lower() == normalized]
        if exact:
            return str(exact[0][id_field])
    matches = [record for record in records if str(record.get(id_field) or "").lower().startswith(normalized)]
    if len(matches) == 1:
        return str(matches[0][id_field])
    if len(matches) > 1:
        candidates = ", ".join(str(record.get(id_field)) for record in matches[:5])
        raise CliError(f"Ambiguous {resource_label} id '{candidate_id}'. Use one of: {candidates}")
    raise CliError(f"Unable to resolve {resource_label} id '{candidate_id}'.")


def _resolve_payload_proposal_references(
    context: CliContext,
    *,
    thread_id: str,
    payload: Any,
    cache: dict[str, str],
    records_state: dict[str, list[dict[str, Any]] | None],
) -> Any:
    if isinstance(payload, dict):
        resolved: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {"create_entry_proposal_id", "create_group_proposal_id"} and isinstance(value, str):
                normalized = value.strip()
                proposal_records = records_state["records"]
                if proposal_records is None:
                    proposal_records = _list_proposals_for_resolution(context, thread_id=thread_id)
                    records_state["records"] = proposal_records
                if normalized not in cache:
                    cache[normalized] = _resolve_id_from_records(
                        records=proposal_records,
                        candidate_id=normalized,
                        resource_label="proposal",
                        id_field="proposal_id",
                    )
                resolved[key] = cache[normalized]
                continue
            resolved[key] = _resolve_payload_proposal_references(
                context,
                thread_id=thread_id,
                payload=value,
                cache=cache,
                records_state=records_state,
            )
        return resolved
    if isinstance(payload, list):
        return [
            _resolve_payload_proposal_references(
                context,
                thread_id=thread_id,
                payload=item,
                cache=cache,
                records_state=records_state,
            )
            for item in payload
        ]
    return payload


def _list_proposals_for_resolution(context: CliContext, *, thread_id: str) -> list[dict[str, Any]]:
    _, payload = request_json(
        context,
        "GET",
        f"/agent/threads/{thread_id}/proposals",
        params={"limit": 5000},
        include_run_id=True,
    )
    records = payload.get("proposals") if isinstance(payload, dict) else []
    return records if isinstance(records, list) else []

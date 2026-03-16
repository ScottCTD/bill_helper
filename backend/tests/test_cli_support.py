from __future__ import annotations

import json

import pytest

from backend.cli import main as cli_main
from backend.cli.rendering import render_output
from backend.cli.support import (
    CliError,
    build_cli_context,
    resolve_entry_id,
    resolve_payload_proposal_references,
    resolve_proposal_id,
    resolve_snapshot_id,
)
from backend.tests.test_entries import create_account, create_entry


def test_build_cli_context_reads_workspace_cli_config_when_env_missing(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "bh-env.json"
    config_path.write_text(
        json.dumps(
            {
                "api_base_url": "http://host.docker.internal:8000/api/v1",
                "auth_token": "workspace-token",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.cli.support._WORKSPACE_CLI_CONFIG_PATH", config_path)
    monkeypatch.delenv("BH_API_BASE_URL", raising=False)
    monkeypatch.delenv("BH_AUTH_TOKEN", raising=False)

    context = build_cli_context(output_format="json")

    assert context.api_base_url == "http://host.docker.internal:8000/api/v1"
    assert context.auth_token == "workspace-token"


def test_build_cli_context_prefers_bh_env_over_workspace_cli_config(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "bh-env.json"
    config_path.write_text(
        json.dumps(
            {
                "api_base_url": "http://from-config/api/v1",
                "auth_token": "config-token",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.cli.support._WORKSPACE_CLI_CONFIG_PATH", config_path)
    monkeypatch.setenv("BH_API_BASE_URL", "http://from-env/api/v1")
    monkeypatch.setenv("BH_AUTH_TOKEN", "env-token")

    context = build_cli_context(output_format="json")

    assert context.api_base_url == "http://from-env/api/v1"
    assert context.auth_token == "env-token"


def test_build_cli_context_raises_helpful_error_when_cli_context_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("backend.cli.support._WORKSPACE_CLI_CONFIG_PATH", tmp_path / "missing.json")
    monkeypatch.delenv("BH_API_BASE_URL", raising=False)
    monkeypatch.delenv("BH_AUTH_TOKEN", raising=False)

    with pytest.raises(CliError) as exc:
        build_cli_context(output_format="json")

    assert "launch the workspace IDE" in str(exc.value)


def test_build_cli_context_defaults_to_compact_when_stdout_is_not_tty(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "bh-env.json"
    config_path.write_text(
        json.dumps({"api_base_url": "http://example/api/v1", "auth_token": "workspace-token"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.cli.support._WORKSPACE_CLI_CONFIG_PATH", config_path)
    monkeypatch.setattr("backend.cli.support.sys.stdout.isatty", lambda: False)

    context = build_cli_context()

    assert context.output_format == "compact"


def test_build_cli_context_defaults_to_text_when_stdout_is_tty(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "bh-env.json"
    config_path.write_text(
        json.dumps({"api_base_url": "http://example/api/v1", "auth_token": "workspace-token"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.cli.support._WORKSPACE_CLI_CONFIG_PATH", config_path)
    monkeypatch.setattr("backend.cli.support.sys.stdout.isatty", lambda: True)

    context = build_cli_context()

    assert context.output_format == "text"


def test_render_output_uses_compact_schema_for_entries_list() -> None:
    rendered = render_output(
        {
            "items": [
                {
                    "id": "12345678-abcd-ef01-2345-6789abcdef01",
                    "occurred_at": "2026-03-12",
                    "kind": "EXPENSE",
                    "amount_minor": 1234,
                    "currency_code": "CAD",
                    "name": "Farm Boy",
                    "from_entity": None,
                    "to_entity": "Farm Boy",
                    "tags": [{"name": "grocery"}],
                }
            ],
            "total": 1,
            "limit": 20,
            "offset": 0,
        },
        output_format="compact",
        render_key="entries_list",
    )

    assert "schema: id|date|kind|amount_minor|currency|name|from|to|tags" in rendered
    assert "12345678|2026-03-12|EXPENSE|1234|CAD|Farm Boy|-|Farm Boy|grocery" in rendered
    assert "color" not in rendered


def test_render_output_falls_back_to_full_id_when_short_ids_collide() -> None:
    rendered = render_output(
        {
            "items": [
                {
                    "id": "12345678-abcd-ef01-2345-6789abcdef01",
                    "occurred_at": "2026-03-12",
                    "kind": "EXPENSE",
                    "amount_minor": 1234,
                    "currency_code": "CAD",
                    "name": "Farm Boy",
                    "from_entity": None,
                    "to_entity": "Farm Boy",
                    "tags": [],
                },
                {
                    "id": "12345678-ffff-ef01-2345-6789abcdef02",
                    "occurred_at": "2026-03-13",
                    "kind": "EXPENSE",
                    "amount_minor": 5678,
                    "currency_code": "CAD",
                    "name": "Metro",
                    "from_entity": None,
                    "to_entity": "Metro",
                    "tags": [],
                },
            ],
            "total": 2,
            "limit": 20,
            "offset": 0,
        },
        output_format="compact",
        render_key="entries_list",
    )

    assert "12345678-abcd-ef01-2345-6789abcdef01" in rendered
    assert "12345678-ffff-ef01-2345-6789abcdef02" in rendered


def test_render_output_uses_renderer_for_accounts_list_payloads() -> None:
    rendered = render_output(
        [
            {
                "id": "12345678-abcd-ef01-2345-6789abcdef01",
                "name": "Checking",
                "currency_code": "USD",
                "is_active": True,
            }
        ],
        output_format="text",
        render_key="accounts_list",
    )

    assert "Accounts" in rendered
    assert "12345678" in rendered
    assert "Checking" in rendered
    assert "'id':" not in rendered


def test_render_output_includes_tag_description_in_compact_and_text() -> None:
    payload = [
        {
            "name": "grocery",
            "type": "expense",
            "description": "Food bought from stores.",
        }
    ]

    compact_rendered = render_output(
        payload,
        output_format="compact",
        render_key="tags_list",
    )
    text_rendered = render_output(
        payload,
        output_format="text",
        render_key="tags_list",
    )

    assert "schema: name|type|description" in compact_rendered
    assert "grocery|expense|Food bought from stores." in compact_rendered
    assert "Description" in text_rendered
    assert "Food bought from stores." in text_rendered


def test_entries_parser_without_subcommand_prints_entries_help(capsys) -> None:
    exit_code = cli_main.main(["entries"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "usage: " in captured.out
    assert "entries [-h] {list,get,create,update,remove}" in captured.out
    assert "threads" not in captured.out


def test_top_level_help_omits_removed_commands() -> None:
    parser = cli_main._build_parser()
    help_text = parser.format_help()

    assert "threads" not in help_text
    assert "reviews" not in help_text
    assert "\n  workspace" not in help_text
    assert "snapshots" in help_text


def test_proposals_parser_includes_update_and_remove(capsys) -> None:
    exit_code = cli_main.main(["proposals"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "proposals [-h] {list,get,update,remove}" in captured.out


def test_resolve_entry_id_accepts_short_prefix(client, monkeypatch) -> None:
    account_id = create_account(client)
    entry = create_entry(client, account_id, "Coffee")
    monkeypatch.setenv("BH_API_BASE_URL", "http://testserver/api/v1")
    monkeypatch.setenv("BH_AUTH_TOKEN", "token")

    def fake_request_json(context, method, path, **kwargs):
        if method == "GET" and path == "/entries":
            response = client.get(
                "/api/v1/entries",
                params=kwargs.get("params"),
            )
        else:
            raise AssertionError(f"Unexpected path: {method} {path}")
        response.raise_for_status()
        return response.status_code, response.json()

    monkeypatch.setattr("backend.cli.support.request_json", fake_request_json)

    resolved = resolve_entry_id(build_cli_context(output_format="json"), entry_id=entry["id"][:8])

    assert resolved == entry["id"]


def test_resolve_proposal_id_accepts_short_prefix(client, monkeypatch) -> None:
    monkeypatch.setenv("BH_API_BASE_URL", "http://testserver/api/v1")
    monkeypatch.setenv("BH_AUTH_TOKEN", "token")
    monkeypatch.setenv("BH_RUN_ID", "run-123")

    def fake_request_json(context, method, path, **kwargs):
        assert method == "GET"
        assert path == "/agent/threads/thread-123/proposals"
        assert kwargs.get("include_run_id") is True
        return 200, {
            "returned_count": 1,
            "total_available": 1,
            "proposals": [
                {
                    "proposal_id": "293272a6-44da-42cc-b2e4-43644a729979",
                    "proposal_short_id": "293272a6",
                }
            ],
        }

    monkeypatch.setattr("backend.cli.support.request_json", fake_request_json)

    resolved = resolve_proposal_id(
        build_cli_context(output_format="json"),
        thread_id="thread-123",
        proposal_id="293272a6",
    )

    assert resolved == "293272a6-44da-42cc-b2e4-43644a729979"


def test_resolve_snapshot_id_accepts_short_prefix(client, monkeypatch) -> None:
    monkeypatch.setenv("BH_API_BASE_URL", "http://testserver/api/v1")
    monkeypatch.setenv("BH_AUTH_TOKEN", "token")

    def fake_request_json(context, method, path, **kwargs):
        assert method == "GET"
        assert path == "/accounts/account-123/snapshots"
        return 200, [
            {
                "id": "4dcbca9e-44da-42cc-b2e4-43644a729979",
                "snapshot_at": "2026-03-15",
                "balance_minor": 12345,
                "note": "statement",
            }
        ]

    monkeypatch.setattr("backend.cli.support.request_json", fake_request_json)

    resolved = resolve_snapshot_id(
        build_cli_context(output_format="json"),
        account_id="account-123",
        snapshot_id="4dcbca9e",
    )

    assert resolved == "4dcbca9e-44da-42cc-b2e4-43644a729979"


def test_resolve_payload_proposal_references_canonicalizes_nested_refs(monkeypatch) -> None:
    monkeypatch.setenv("BH_API_BASE_URL", "http://testserver/api/v1")
    monkeypatch.setenv("BH_AUTH_TOKEN", "token")
    monkeypatch.setenv("BH_RUN_ID", "run-123")

    request_count = 0

    def fake_request_json(context, method, path, **kwargs):
        nonlocal request_count
        request_count += 1
        assert method == "GET"
        assert path == "/agent/threads/thread-123/proposals"
        assert kwargs.get("include_run_id") is True
        return 200, {
            "returned_count": 2,
            "total_available": 2,
            "proposals": [
                {
                    "proposal_id": "293272a6-44da-42cc-b2e4-43644a729979",
                    "proposal_short_id": "293272a6",
                },
                {
                    "proposal_id": "70dcb3a0-c965-44b3-a041-6d5a8a3d2c8c",
                    "proposal_short_id": "70dcb3a0",
                },
            ],
        }

    monkeypatch.setattr("backend.cli.support.request_json", fake_request_json)

    resolved = resolve_payload_proposal_references(
        build_cli_context(output_format="json"),
        thread_id="thread-123",
        payload={
            "group_ref": {"create_group_proposal_id": "293272a6"},
            "target": {
                "target_type": "entry",
                "entry_ref": {"create_entry_proposal_id": "70dcb3a0"},
            },
        },
    )

    assert resolved == {
        "group_ref": {"create_group_proposal_id": "293272a6-44da-42cc-b2e4-43644a729979"},
        "target": {
            "target_type": "entry",
            "entry_ref": {"create_entry_proposal_id": "70dcb3a0-c965-44b3-a041-6d5a8a3d2c8c"},
        },
    }
    assert request_count == 1


def test_group_and_account_lists_render_short_ids() -> None:
    accounts_rendered = render_output(
        [
            {
                "id": "abcdef12-1234-5678-90ab-cdef12345678",
                "name": "Main Checking",
                "currency_code": "USD",
                "is_active": True,
            }
        ],
        output_format="compact",
        render_key="accounts_list",
    )
    groups_rendered = render_output(
        [
            {
                "id": "fedcba98-1234-5678-90ab-cdef12345678",
                "group_type": "BUNDLE",
                "name": "Bills",
                "descendant_entry_count": 3,
                "first_occurred_at": "2026-01-01",
                "last_occurred_at": "2026-03-01",
            }
        ],
        output_format="compact",
        render_key="groups_list",
    )

    assert "abcdef12|Main Checking|USD|true" in accounts_rendered
    assert "fedcba98|BUNDLE|Bills|3|2026-01-01|2026-03-01" in groups_rendered

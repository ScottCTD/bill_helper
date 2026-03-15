"""`billengine` CLI entrypoint.

CALLING SPEC:
    main(argv=None) -> int

Inputs:
    - command-line argv plus env-provided backend/auth/thread/run defaults
Outputs:
    - exit code, stdout/stderr output
Side effects:
    - performs HTTP calls to the Bill Helper backend and prints results
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from backend.cli.support import (
    CliContext,
    CliError,
    build_cli_context,
    load_json_argument,
    print_output,
    request_json,
    resolve_proposal_id,
    resolve_thread_id,
)


CommandHandler = Callable[[argparse.Namespace, CliContext], Any]


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 1

    try:
        context = build_cli_context(output_format=args.output_format)
        payload = args.handler(args, context)
    except CliError as exc:
        print(str(exc), file=__import__("sys").stderr)
        return exc.exit_code

    print_output(payload, output_format=context.output_format)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent-first Bill Helper CLI.")
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default=None,
        dest="output_format",
        help="Output format. Defaults to json for non-TTY and text for TTY.",
    )
    subparsers = parser.add_subparsers(dest="command")

    _build_status_parser(subparsers)
    _build_threads_parser(subparsers)
    _build_entries_parser(subparsers)
    _build_accounts_parser(subparsers)
    _build_groups_parser(subparsers)
    _build_entities_parser(subparsers)
    _build_tags_parser(subparsers)
    _build_proposals_parser(subparsers)
    _build_reviews_parser(subparsers)
    _build_workspace_parser(subparsers)
    return parser


def _build_status_parser(subparsers) -> None:
    parser = subparsers.add_parser("status", help="Show current auth/workspace/CLI context.")
    parser.set_defaults(handler=_handle_status)


def _build_threads_parser(subparsers) -> None:
    parser = subparsers.add_parser("threads", help="Thread operations.")
    threads = parser.add_subparsers(dest="threads_command")

    list_parser = threads.add_parser("list", help="List threads.")
    list_parser.set_defaults(handler=_handle_threads_list)

    show_parser = threads.add_parser("show", help="Show one thread.")
    show_parser.add_argument("thread_id")
    show_parser.set_defaults(handler=_handle_threads_show)

    create_parser = threads.add_parser("create", help="Create a thread.")
    create_parser.add_argument("--title", default=None)
    create_parser.set_defaults(handler=_handle_threads_create)

    rename_parser = threads.add_parser("rename", help="Rename a thread.")
    rename_parser.add_argument("thread_id")
    rename_parser.add_argument("--title", required=True)
    rename_parser.set_defaults(handler=_handle_threads_rename)


def _build_entries_parser(subparsers) -> None:
    parser = subparsers.add_parser("entries", help="Entry reads.")
    entries = parser.add_subparsers(dest="entries_command")

    list_parser = entries.add_parser("list", help="List entries.")
    list_parser.add_argument("--start-date", default=None)
    list_parser.add_argument("--end-date", default=None)
    list_parser.add_argument("--kind", default=None)
    list_parser.add_argument("--currency", default=None)
    list_parser.add_argument("--account-id", default=None)
    list_parser.add_argument("--source", default=None)
    list_parser.add_argument("--tag", default=None)
    list_parser.add_argument("--filter-group-id", default=None)
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--offset", type=int, default=0)
    list_parser.set_defaults(handler=_handle_entries_list)

    get_parser = entries.add_parser("get", help="Get one entry.")
    get_parser.add_argument("entry_id")
    get_parser.set_defaults(handler=_handle_entries_get)


def _build_accounts_parser(subparsers) -> None:
    parser = subparsers.add_parser("accounts", help="Account reads.")
    accounts = parser.add_subparsers(dest="accounts_command")

    list_parser = accounts.add_parser("list", help="List accounts.")
    list_parser.set_defaults(handler=_handle_accounts_list)

    snapshots_parser = accounts.add_parser("snapshots", help="List account snapshots.")
    snapshots_parser.add_argument("account_id")
    snapshots_parser.set_defaults(handler=_handle_accounts_snapshots)

    recon_parser = accounts.add_parser("reconciliation", help="Get account reconciliation.")
    recon_parser.add_argument("account_id")
    recon_parser.add_argument("--as-of", default=None)
    recon_parser.set_defaults(handler=_handle_accounts_reconciliation)


def _build_groups_parser(subparsers) -> None:
    parser = subparsers.add_parser("groups", help="Group reads.")
    groups = parser.add_subparsers(dest="groups_command")

    list_parser = groups.add_parser("list", help="List groups.")
    list_parser.set_defaults(handler=_handle_groups_list)

    get_parser = groups.add_parser("get", help="Get one group graph.")
    get_parser.add_argument("group_id")
    get_parser.set_defaults(handler=_handle_groups_get)


def _build_entities_parser(subparsers) -> None:
    parser = subparsers.add_parser("entities", help="Entity reads.")
    entities = parser.add_subparsers(dest="entities_command")

    list_parser = entities.add_parser("list", help="List entities.")
    list_parser.set_defaults(handler=_handle_entities_list)


def _build_tags_parser(subparsers) -> None:
    parser = subparsers.add_parser("tags", help="Tag reads.")
    tags = parser.add_subparsers(dest="tags_command")

    list_parser = tags.add_parser("list", help="List tags.")
    list_parser.set_defaults(handler=_handle_tags_list)


def _build_proposals_parser(subparsers) -> None:
    parser = subparsers.add_parser("proposals", help="Thread-scoped proposal operations.")
    proposals = parser.add_subparsers(dest="proposals_command")

    list_parser = proposals.add_parser("list", help="List proposals in the current thread.")
    _add_thread_override(list_parser)
    list_parser.add_argument("--proposal-type", default=None)
    list_parser.add_argument("--proposal-status", default=None)
    list_parser.add_argument("--change-action", default=None)
    list_parser.add_argument("--proposal-id", default=None)
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.set_defaults(handler=_handle_proposals_list)

    get_parser = proposals.add_parser("get", help="Get one proposal by full id or unique prefix.")
    _add_thread_override(get_parser)
    get_parser.add_argument("proposal_id")
    get_parser.set_defaults(handler=_handle_proposals_get)

    create_parser = proposals.add_parser("create", help="Create one proposal in the current thread.")
    _add_thread_override(create_parser)
    create_parser.add_argument("change_type")
    _add_json_options(create_parser, inline_flag="--payload-json", file_flag="--payload-file", dest="payload")
    create_parser.set_defaults(handler=_handle_proposals_create)

    update_parser = proposals.add_parser("update", help="Update one pending proposal.")
    _add_thread_override(update_parser)
    update_parser.add_argument("proposal_id")
    _add_json_options(update_parser, inline_flag="--patch-json", file_flag="--patch-file", dest="patch")
    update_parser.set_defaults(handler=_handle_proposals_update)

    remove_parser = proposals.add_parser("remove", help="Remove one pending proposal.")
    _add_thread_override(remove_parser)
    remove_parser.add_argument("proposal_id")
    remove_parser.set_defaults(handler=_handle_proposals_remove)


def _build_reviews_parser(subparsers) -> None:
    parser = subparsers.add_parser("reviews", help="Review actions for proposals.")
    reviews = parser.add_subparsers(dest="reviews_command")
    for action in ("approve", "reject", "reopen"):
        review_parser = reviews.add_parser(action, help=f"{action.title()} one proposal.")
        _add_thread_override(review_parser)
        review_parser.add_argument("proposal_id")
        review_parser.add_argument("--note", default=None)
        _add_json_options(
            review_parser,
            inline_flag="--override-json",
            file_flag="--override-file",
            dest="override",
            required=False,
        )
        review_parser.set_defaults(handler=_handle_review_action, review_action=action)


def _build_workspace_parser(subparsers) -> None:
    parser = subparsers.add_parser("workspace", help="Workspace status.")
    workspace = parser.add_subparsers(dest="workspace_command")

    status_parser = workspace.add_parser("status", help="Get workspace status.")
    status_parser.set_defaults(handler=_handle_workspace_status)


def _add_thread_override(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--thread", default=None)


def _add_json_options(
    parser: argparse.ArgumentParser,
    *,
    inline_flag: str,
    file_flag: str,
    dest: str,
    required: bool = True,
) -> None:
    group = parser.add_mutually_exclusive_group(required=required)
    group.add_argument(inline_flag, dest=f"{dest}_json", default=None)
    group.add_argument(file_flag, dest=f"{dest}_file", default=None)


def _handle_status(_args: argparse.Namespace, context: CliContext) -> dict[str, Any]:
    _, me = request_json(context, "GET", "/auth/me")
    _, workspace = request_json(context, "GET", "/workspace")
    return {
        "auth": me,
        "workspace": workspace,
        "context": {
            "thread_id": context.thread_id,
            "run_id": context.run_id,
            "api_base_url": context.api_base_url,
        },
    }


def _handle_threads_list(_args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", "/agent/threads")
    return payload


def _handle_threads_show(args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", f"/agent/threads/{args.thread_id}")
    return payload


def _handle_threads_create(args: argparse.Namespace, context: CliContext) -> Any:
    body = {"title": args.title} if args.title else {}
    _, payload = request_json(context, "POST", "/agent/threads", json_body=body)
    return payload


def _handle_threads_rename(args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(
        context,
        "PATCH",
        f"/agent/threads/{args.thread_id}",
        json_body={"title": args.title},
    )
    return payload


def _handle_entries_list(args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(
        context,
        "GET",
        "/entries",
        params={
            "start_date": args.start_date,
            "end_date": args.end_date,
            "kind": args.kind,
            "currency": args.currency,
            "account_id": args.account_id,
            "source": args.source,
            "tag": args.tag,
            "filter_group_id": args.filter_group_id,
            "limit": args.limit,
            "offset": args.offset,
        },
    )
    return payload


def _handle_entries_get(args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", f"/entries/{args.entry_id}")
    return payload


def _handle_accounts_list(_args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", "/accounts")
    return payload


def _handle_accounts_snapshots(args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", f"/accounts/{args.account_id}/snapshots")
    return payload


def _handle_accounts_reconciliation(args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(
        context,
        "GET",
        f"/accounts/{args.account_id}/reconciliation",
        params={"as_of": args.as_of},
    )
    return payload


def _handle_groups_list(_args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", "/groups")
    return payload


def _handle_groups_get(args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", f"/groups/{args.group_id}")
    return payload


def _handle_entities_list(_args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", "/entities")
    return payload


def _handle_tags_list(_args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", "/tags")
    return payload


def _handle_proposals_list(args: argparse.Namespace, context: CliContext) -> Any:
    thread_id = resolve_thread_id(context, override=args.thread)
    _, payload = request_json(
        context,
        "GET",
        f"/agent/threads/{thread_id}/proposals",
        params={
            "proposal_type": args.proposal_type,
            "proposal_status": args.proposal_status,
            "change_action": args.change_action,
            "proposal_id": args.proposal_id,
            "limit": args.limit,
        },
        include_run_id=True,
    )
    return payload


def _handle_proposals_get(args: argparse.Namespace, context: CliContext) -> Any:
    thread_id = resolve_thread_id(context, override=args.thread)
    _, payload = request_json(
        context,
        "GET",
        f"/agent/threads/{thread_id}/proposals/{args.proposal_id}",
        include_run_id=True,
    )
    return payload


def _handle_proposals_create(args: argparse.Namespace, context: CliContext) -> Any:
    thread_id = resolve_thread_id(context, override=args.thread)
    payload_json = load_json_argument(inline_json=args.payload_json, json_file=args.payload_file)
    _, payload = request_json(
        context,
        "POST",
        f"/agent/threads/{thread_id}/proposals",
        json_body={
            "change_type": args.change_type,
            "payload_json": payload_json,
        },
        include_run_id=True,
    )
    return payload


def _handle_proposals_update(args: argparse.Namespace, context: CliContext) -> Any:
    thread_id = resolve_thread_id(context, override=args.thread)
    patch_map = load_json_argument(inline_json=args.patch_json, json_file=args.patch_file)
    _, payload = request_json(
        context,
        "PATCH",
        f"/agent/threads/{thread_id}/proposals/{args.proposal_id}",
        json_body={"patch_map": patch_map},
        include_run_id=True,
    )
    return payload


def _handle_proposals_remove(args: argparse.Namespace, context: CliContext) -> Any:
    thread_id = resolve_thread_id(context, override=args.thread)
    _, payload = request_json(
        context,
        "DELETE",
        f"/agent/threads/{thread_id}/proposals/{args.proposal_id}",
        include_run_id=True,
    )
    return payload


def _handle_review_action(args: argparse.Namespace, context: CliContext) -> Any:
    thread_id = resolve_thread_id(context, override=args.thread)
    resolved_id = resolve_proposal_id(context, thread_id=thread_id, proposal_id=args.proposal_id)
    override_payload = None
    if args.override_json is not None or args.override_file is not None:
        override_payload = load_json_argument(inline_json=args.override_json, json_file=args.override_file)
    _, payload = request_json(
        context,
        "POST",
        f"/agent/change-items/{resolved_id}/{args.review_action}",
        json_body={
            "note": args.note,
            "payload_override": override_payload,
        },
    )
    return payload


def _handle_workspace_status(_args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", "/workspace")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())

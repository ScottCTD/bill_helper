"""`bh` CLI entrypoint.

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
from typing import Any

from backend.cli.support import (
    CliContext,
    CliError,
    build_cli_context,
    load_json_argument,
    print_output,
    request_json,
    resolve_account_id,
    resolve_account_name,
    resolve_entry_id,
    resolve_group_id,
    resolve_proposal_id,
    resolve_thread_id,
)


CommandHandler = Callable[[argparse.Namespace, CliContext], Any]


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        help_parser = getattr(args, "help_parser", None)
        if isinstance(help_parser, argparse.ArgumentParser):
            help_parser.print_help()
            return 1
        parser.print_help()
        return 1

    try:
        context = build_cli_context(output_format=args.output_format)
        payload = args.handler(args, context)
    except CliError as exc:
        print(str(exc), file=__import__("sys").stderr)
        return exc.exit_code

    print_output(payload, output_format=context.output_format, render_key=getattr(args, "render_key", None))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bh", description="Agent-first Bill Helper CLI.")
    _add_format_option(parser)
    subparsers = parser.add_subparsers(dest="command")

    _build_status_parser(subparsers)
    _build_entries_parser(subparsers)
    _build_accounts_parser(subparsers)
    _build_groups_parser(subparsers)
    _build_entities_parser(subparsers)
    _build_tags_parser(subparsers)
    _build_proposals_parser(subparsers)
    return parser


def _build_status_parser(subparsers) -> None:
    parser = subparsers.add_parser("status", help="Show current auth/workspace/CLI context.")
    _add_format_option(parser)
    parser.set_defaults(handler=_handle_status, render_key="status")


def _build_entries_parser(subparsers) -> None:
    parser = subparsers.add_parser("entries", help="Entry reads and entry proposal commands.")
    parser.set_defaults(help_parser=parser)
    entries = parser.add_subparsers(dest="entries_command")

    list_parser = entries.add_parser("list", help="List entries.")
    _add_format_option(list_parser)
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
    list_parser.set_defaults(handler=_handle_entries_list, render_key="entries_list")

    get_parser = entries.add_parser("get", help="Get one entry.")
    _add_format_option(get_parser)
    get_parser.add_argument("entry_id")
    get_parser.set_defaults(handler=_handle_entries_get, render_key="entries_detail")

    create_parser = entries.add_parser("create", help="Create an entry proposal in the current thread.")
    _add_format_option(create_parser)
    _add_json_options(create_parser, inline_flag="--payload-json", file_flag="--payload-file", dest="payload")
    create_parser.set_defaults(handler=_handle_entries_create, render_key="proposals_detail")

    update_parser = entries.add_parser("update", help="Create an entry-update proposal in the current thread.")
    _add_format_option(update_parser)
    update_parser.add_argument("entry_id")
    _add_json_options(update_parser, inline_flag="--patch-json", file_flag="--patch-file", dest="patch")
    update_parser.set_defaults(handler=_handle_entries_update, render_key="proposals_detail")

    remove_parser = entries.add_parser("remove", help="Create an entry-delete proposal in the current thread.")
    _add_format_option(remove_parser)
    remove_parser.add_argument("entry_id")
    remove_parser.set_defaults(handler=_handle_entries_remove, render_key="proposals_detail")


def _build_accounts_parser(subparsers) -> None:
    parser = subparsers.add_parser("accounts", help="Account reads and account proposal commands.")
    parser.set_defaults(help_parser=parser)
    accounts = parser.add_subparsers(dest="accounts_command")

    list_parser = accounts.add_parser("list", help="List accounts.")
    _add_format_option(list_parser)
    list_parser.set_defaults(handler=_handle_accounts_list, render_key="accounts_list")

    snapshots_parser = accounts.add_parser("snapshots", help="List account snapshots.")
    _add_format_option(snapshots_parser)
    snapshots_parser.add_argument("account_id")
    snapshots_parser.set_defaults(handler=_handle_accounts_snapshots, render_key="accounts_snapshots")

    recon_parser = accounts.add_parser("reconciliation", help="Get account reconciliation.")
    _add_format_option(recon_parser)
    recon_parser.add_argument("account_id")
    recon_parser.add_argument("--as-of", default=None)
    recon_parser.set_defaults(handler=_handle_accounts_reconciliation, render_key="accounts_reconciliation")

    create_parser = accounts.add_parser("create", help="Create an account proposal in the current thread.")
    _add_format_option(create_parser)
    _add_json_options(create_parser, inline_flag="--payload-json", file_flag="--payload-file", dest="payload")
    create_parser.set_defaults(handler=_handle_accounts_create, render_key="proposals_detail")

    update_parser = accounts.add_parser("update", help="Create an account-update proposal in the current thread.")
    _add_format_option(update_parser)
    update_parser.add_argument("account_ref")
    _add_json_options(update_parser, inline_flag="--patch-json", file_flag="--patch-file", dest="patch")
    update_parser.set_defaults(handler=_handle_accounts_update, render_key="proposals_detail")

    remove_parser = accounts.add_parser("remove", help="Create an account-delete proposal in the current thread.")
    _add_format_option(remove_parser)
    remove_parser.add_argument("account_ref")
    remove_parser.set_defaults(handler=_handle_accounts_remove, render_key="proposals_detail")


def _build_groups_parser(subparsers) -> None:
    parser = subparsers.add_parser("groups", help="Group reads and group proposal commands.")
    parser.set_defaults(help_parser=parser)
    groups = parser.add_subparsers(dest="groups_command")

    list_parser = groups.add_parser("list", help="List groups.")
    _add_format_option(list_parser)
    list_parser.set_defaults(handler=_handle_groups_list, render_key="groups_list")

    get_parser = groups.add_parser("get", help="Get one group graph.")
    _add_format_option(get_parser)
    get_parser.add_argument("group_id")
    get_parser.set_defaults(handler=_handle_groups_get, render_key="groups_detail")

    create_parser = groups.add_parser("create", help="Create a group proposal in the current thread.")
    _add_format_option(create_parser)
    _add_json_options(create_parser, inline_flag="--payload-json", file_flag="--payload-file", dest="payload")
    create_parser.set_defaults(handler=_handle_groups_create, render_key="proposals_detail")

    update_parser = groups.add_parser("update", help="Create a group-update proposal in the current thread.")
    _add_format_option(update_parser)
    update_parser.add_argument("group_id")
    _add_json_options(update_parser, inline_flag="--patch-json", file_flag="--patch-file", dest="patch")
    update_parser.set_defaults(handler=_handle_groups_update, render_key="proposals_detail")

    remove_parser = groups.add_parser("remove", help="Create a group-delete proposal in the current thread.")
    _add_format_option(remove_parser)
    remove_parser.add_argument("group_id")
    remove_parser.set_defaults(handler=_handle_groups_remove, render_key="proposals_detail")

    add_member_parser = groups.add_parser("add-member", help="Create a group-membership add proposal.")
    _add_format_option(add_member_parser)
    _add_json_options(add_member_parser, inline_flag="--payload-json", file_flag="--payload-file", dest="payload")
    add_member_parser.set_defaults(handler=_handle_groups_add_member, render_key="proposals_detail")

    remove_member_parser = groups.add_parser("remove-member", help="Create a group-membership removal proposal.")
    _add_format_option(remove_member_parser)
    _add_json_options(remove_member_parser, inline_flag="--payload-json", file_flag="--payload-file", dest="payload")
    remove_member_parser.set_defaults(handler=_handle_groups_remove_member, render_key="proposals_detail")


def _build_entities_parser(subparsers) -> None:
    parser = subparsers.add_parser("entities", help="Entity reads and entity proposal commands.")
    parser.set_defaults(help_parser=parser)
    entities = parser.add_subparsers(dest="entities_command")

    list_parser = entities.add_parser("list", help="List entities.")
    _add_format_option(list_parser)
    list_parser.set_defaults(handler=_handle_entities_list, render_key="entities_list")

    create_parser = entities.add_parser("create", help="Create an entity proposal in the current thread.")
    _add_format_option(create_parser)
    _add_json_options(create_parser, inline_flag="--payload-json", file_flag="--payload-file", dest="payload")
    create_parser.set_defaults(handler=_handle_entities_create, render_key="proposals_detail")

    update_parser = entities.add_parser("update", help="Create an entity-update proposal in the current thread.")
    _add_format_option(update_parser)
    update_parser.add_argument("entity_name")
    _add_json_options(update_parser, inline_flag="--patch-json", file_flag="--patch-file", dest="patch")
    update_parser.set_defaults(handler=_handle_entities_update, render_key="proposals_detail")

    remove_parser = entities.add_parser("remove", help="Create an entity-delete proposal in the current thread.")
    _add_format_option(remove_parser)
    remove_parser.add_argument("entity_name")
    remove_parser.set_defaults(handler=_handle_entities_remove, render_key="proposals_detail")


def _build_tags_parser(subparsers) -> None:
    parser = subparsers.add_parser("tags", help="Tag reads and tag proposal commands.")
    parser.set_defaults(help_parser=parser)
    tags = parser.add_subparsers(dest="tags_command")

    list_parser = tags.add_parser("list", help="List tags.")
    _add_format_option(list_parser)
    list_parser.set_defaults(handler=_handle_tags_list, render_key="tags_list")

    create_parser = tags.add_parser("create", help="Create a tag proposal in the current thread.")
    _add_format_option(create_parser)
    _add_json_options(create_parser, inline_flag="--payload-json", file_flag="--payload-file", dest="payload")
    create_parser.set_defaults(handler=_handle_tags_create, render_key="proposals_detail")

    update_parser = tags.add_parser("update", help="Create a tag-update proposal in the current thread.")
    _add_format_option(update_parser)
    update_parser.add_argument("tag_name")
    _add_json_options(update_parser, inline_flag="--patch-json", file_flag="--patch-file", dest="patch")
    update_parser.set_defaults(handler=_handle_tags_update, render_key="proposals_detail")

    remove_parser = tags.add_parser("remove", help="Create a tag-delete proposal in the current thread.")
    _add_format_option(remove_parser)
    remove_parser.add_argument("tag_name")
    remove_parser.set_defaults(handler=_handle_tags_remove, render_key="proposals_detail")


def _build_proposals_parser(subparsers) -> None:
    parser = subparsers.add_parser("proposals", help="Current-thread proposal inspection.")
    parser.set_defaults(help_parser=parser)
    proposals = parser.add_subparsers(dest="proposals_command")

    list_parser = proposals.add_parser("list", help="List proposals in the current thread.")
    _add_format_option(list_parser)
    list_parser.add_argument("--proposal-type", default=None)
    list_parser.add_argument("--proposal-status", default=None)
    list_parser.add_argument("--change-action", default=None)
    list_parser.add_argument("--proposal-id", default=None)
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.set_defaults(handler=_handle_proposals_list, render_key="proposals_list")

    get_parser = proposals.add_parser("get", help="Get one proposal by full id or unique prefix.")
    _add_format_option(get_parser)
    get_parser.add_argument("proposal_id")
    get_parser.set_defaults(handler=_handle_proposals_get, render_key="proposals_detail")


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


def _add_format_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=("compact", "json", "text"),
        default=None,
        dest="output_format",
        help="Output format. Agent calls default to compact; text and json are explicit overrides.",
    )


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


def _handle_entries_list(args: argparse.Namespace, context: CliContext) -> Any:
    resolved_account_id = resolve_account_id(context, account_id=args.account_id) if args.account_id is not None else None
    resolved_group_id = resolve_group_id(context, group_id=args.filter_group_id) if args.filter_group_id is not None else None
    _, payload = request_json(
        context,
        "GET",
        "/entries",
        params={
            "start_date": args.start_date,
            "end_date": args.end_date,
            "kind": args.kind,
            "currency": args.currency,
            "account_id": resolved_account_id,
            "source": args.source,
            "tag": args.tag,
            "filter_group_id": resolved_group_id,
            "limit": args.limit,
            "offset": args.offset,
        },
    )
    return payload


def _handle_entries_get(args: argparse.Namespace, context: CliContext) -> Any:
    resolved_id = resolve_entry_id(context, entry_id=args.entry_id)
    _, payload = request_json(context, "GET", f"/entries/{resolved_id}")
    return payload


def _handle_accounts_list(_args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", "/accounts")
    return payload


def _handle_accounts_snapshots(args: argparse.Namespace, context: CliContext) -> Any:
    resolved_id = resolve_account_id(context, account_id=args.account_id)
    _, payload = request_json(context, "GET", f"/accounts/{resolved_id}/snapshots")
    return payload


def _handle_accounts_reconciliation(args: argparse.Namespace, context: CliContext) -> Any:
    resolved_id = resolve_account_id(context, account_id=args.account_id)
    _, payload = request_json(
        context,
        "GET",
        f"/accounts/{resolved_id}/reconciliation",
        params={"as_of": args.as_of},
    )
    return payload


def _handle_groups_list(_args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", "/groups")
    return payload


def _handle_groups_get(args: argparse.Namespace, context: CliContext) -> Any:
    resolved_id = resolve_group_id(context, group_id=args.group_id)
    _, payload = request_json(context, "GET", f"/groups/{resolved_id}")
    return payload


def _handle_entities_list(_args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", "/entities")
    return payload


def _handle_tags_list(_args: argparse.Namespace, context: CliContext) -> Any:
    _, payload = request_json(context, "GET", "/tags")
    return payload


def _handle_entries_create(args: argparse.Namespace, context: CliContext) -> Any:
    payload_json = load_json_argument(inline_json=args.payload_json, json_file=args.payload_file)
    return _create_thread_proposal(context, change_type="create_entry", payload_json=payload_json)


def _handle_entries_update(args: argparse.Namespace, context: CliContext) -> Any:
    patch_map = load_json_argument(inline_json=args.patch_json, json_file=args.patch_file)
    entry_id = resolve_entry_id(context, entry_id=args.entry_id)
    return _create_thread_proposal(
        context,
        change_type="update_entry",
        payload_json={"entry_id": entry_id, "patch": patch_map},
    )


def _handle_entries_remove(args: argparse.Namespace, context: CliContext) -> Any:
    entry_id = resolve_entry_id(context, entry_id=args.entry_id)
    return _create_thread_proposal(context, change_type="delete_entry", payload_json={"entry_id": entry_id})


def _handle_accounts_create(args: argparse.Namespace, context: CliContext) -> Any:
    payload_json = load_json_argument(inline_json=args.payload_json, json_file=args.payload_file)
    return _create_thread_proposal(context, change_type="create_account", payload_json=payload_json)


def _handle_accounts_update(args: argparse.Namespace, context: CliContext) -> Any:
    patch_map = load_json_argument(inline_json=args.patch_json, json_file=args.patch_file)
    account_name = resolve_account_name(context, account_ref=args.account_ref)
    return _create_thread_proposal(
        context,
        change_type="update_account",
        payload_json={"name": account_name, "patch": patch_map},
    )


def _handle_accounts_remove(args: argparse.Namespace, context: CliContext) -> Any:
    account_name = resolve_account_name(context, account_ref=args.account_ref)
    return _create_thread_proposal(context, change_type="delete_account", payload_json={"name": account_name})


def _handle_groups_create(args: argparse.Namespace, context: CliContext) -> Any:
    payload_json = load_json_argument(inline_json=args.payload_json, json_file=args.payload_file)
    return _create_thread_proposal(context, change_type="create_group", payload_json=payload_json)


def _handle_groups_update(args: argparse.Namespace, context: CliContext) -> Any:
    patch_map = load_json_argument(inline_json=args.patch_json, json_file=args.patch_file)
    group_id = resolve_group_id(context, group_id=args.group_id)
    return _create_thread_proposal(
        context,
        change_type="update_group",
        payload_json={"group_id": group_id, "patch": patch_map},
    )


def _handle_groups_remove(args: argparse.Namespace, context: CliContext) -> Any:
    group_id = resolve_group_id(context, group_id=args.group_id)
    return _create_thread_proposal(context, change_type="delete_group", payload_json={"group_id": group_id})


def _handle_groups_add_member(args: argparse.Namespace, context: CliContext) -> Any:
    payload_json = load_json_argument(inline_json=args.payload_json, json_file=args.payload_file)
    return _create_thread_proposal(context, change_type="create_group_member", payload_json=payload_json)


def _handle_groups_remove_member(args: argparse.Namespace, context: CliContext) -> Any:
    payload_json = load_json_argument(inline_json=args.payload_json, json_file=args.payload_file)
    return _create_thread_proposal(context, change_type="delete_group_member", payload_json=payload_json)


def _handle_entities_create(args: argparse.Namespace, context: CliContext) -> Any:
    payload_json = load_json_argument(inline_json=args.payload_json, json_file=args.payload_file)
    return _create_thread_proposal(context, change_type="create_entity", payload_json=payload_json)


def _handle_entities_update(args: argparse.Namespace, context: CliContext) -> Any:
    patch_map = load_json_argument(inline_json=args.patch_json, json_file=args.patch_file)
    return _create_thread_proposal(
        context,
        change_type="update_entity",
        payload_json={"name": args.entity_name, "patch": patch_map},
    )


def _handle_entities_remove(args: argparse.Namespace, context: CliContext) -> Any:
    return _create_thread_proposal(context, change_type="delete_entity", payload_json={"name": args.entity_name})


def _handle_tags_create(args: argparse.Namespace, context: CliContext) -> Any:
    payload_json = load_json_argument(inline_json=args.payload_json, json_file=args.payload_file)
    return _create_thread_proposal(context, change_type="create_tag", payload_json=payload_json)


def _handle_tags_update(args: argparse.Namespace, context: CliContext) -> Any:
    patch_map = load_json_argument(inline_json=args.patch_json, json_file=args.patch_file)
    return _create_thread_proposal(
        context,
        change_type="update_tag",
        payload_json={"name": args.tag_name, "patch": patch_map},
    )


def _handle_tags_remove(args: argparse.Namespace, context: CliContext) -> Any:
    return _create_thread_proposal(context, change_type="delete_tag", payload_json={"name": args.tag_name})


def _handle_proposals_list(args: argparse.Namespace, context: CliContext) -> Any:
    thread_id = resolve_thread_id(context)
    resolved_proposal_id = (
        resolve_proposal_id(context, thread_id=thread_id, proposal_id=args.proposal_id)
        if args.proposal_id is not None
        else None
    )
    _, payload = request_json(
        context,
        "GET",
        f"/agent/threads/{thread_id}/proposals",
        params={
            "proposal_type": args.proposal_type,
            "proposal_status": args.proposal_status,
            "change_action": args.change_action,
            "proposal_id": resolved_proposal_id,
            "limit": args.limit,
        },
        include_run_id=True,
    )
    return payload


def _handle_proposals_get(args: argparse.Namespace, context: CliContext) -> Any:
    thread_id = resolve_thread_id(context)
    resolved_proposal_id = resolve_proposal_id(context, thread_id=thread_id, proposal_id=args.proposal_id)
    _, payload = request_json(
        context,
        "GET",
        f"/agent/threads/{thread_id}/proposals/{resolved_proposal_id}",
        include_run_id=True,
    )
    return payload


def _create_thread_proposal(context: CliContext, *, change_type: str, payload_json: Any) -> Any:
    thread_id = resolve_thread_id(context)
    _, payload = request_json(
        context,
        "POST",
        f"/agent/threads/{thread_id}/proposals",
        json_body={"change_type": change_type, "payload_json": payload_json},
        include_run_id=True,
    )
    return payload


if __name__ == "__main__":
    raise SystemExit(main())

"""Create-command specs and payload helpers for the `bh` CLI.

CALLING SPEC:
    add_create_command_arguments(parser, spec) -> None
    build_validated_create_payload(spec, args, context) -> dict[str, Any]
    format_create_request_error(resource_label, status_code, detail) -> str

Inputs:
    - argparse parsers/namespaces plus CLI context for resource-backed normalization
Outputs:
    - create-command parser wiring, validated proposal payloads, and user-facing error text
Side effects:
    - none
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from backend.services.agent.change_contracts.catalog import (
    CreateAccountPayload,
    CreateEntityPayload,
    CreateTagPayload,
    ProposeCreateSnapshotArgs,
)
from backend.services.agent.change_contracts.entries import CreateEntryPayload
from backend.services.agent.change_contracts.groups import CreateGroupPayload
from backend.cli.support import CliContext, CliError, resolve_account_id


_PYDANTIC_LINK_PATTERN = re.compile(r"https?://errors\.pydantic\.dev/\S+")
_PYDANTIC_METADATA_PATTERN = re.compile(r"\s*\[type=[^\]]+\]")
_PYDANTIC_HEADER_PATTERN = re.compile(r"^(Invalid proposal payload:\s*)?\d+ validation errors? for .+$")


@dataclass(frozen=True, slots=True)
class CreateFieldSpec:
    flags: tuple[str, ...]
    payload_field: str
    argument_kwargs: dict[str, Any]
    required: bool = False
    exclusive_group: str | None = None

    @property
    def primary_flag(self) -> str:
        for flag in self.flags:
            if flag.startswith("--"):
                return flag
        return self.flags[0]


@dataclass(frozen=True, slots=True)
class CreateCommandSpec:
    command_name: str
    resource_label: str
    change_type: str
    help_text: str
    description: str
    epilog: str
    validation_model: type[BaseModel]
    payload_builder: Any
    fields: tuple[CreateFieldSpec, ...]
    parser_defaults: dict[str, Any] = field(default_factory=dict)

    @property
    def field_flag_map(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for item in self.fields:
            mapping.setdefault(item.payload_field, item.primary_flag)
        return mapping


def add_create_command_arguments(parser: argparse.ArgumentParser, spec: CreateCommandSpec) -> None:
    parser.description = spec.description
    parser.epilog = spec.epilog
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.set_defaults(create_command_spec=spec, **spec.parser_defaults)

    required_group = parser.add_argument_group("Required fields")
    optional_group = parser.add_argument_group("Optional fields")
    exclusive_groups: dict[tuple[str, str], Any] = {}

    for item in spec.fields:
        target_group = required_group if item.required else optional_group
        kwargs = dict(item.argument_kwargs)
        if item.exclusive_group is None:
            if item.required:
                kwargs["required"] = True
            target_group.add_argument(*item.flags, **kwargs)
            continue
        group_key = (target_group.title, item.exclusive_group)
        exclusive_group = exclusive_groups.get(group_key)
        if exclusive_group is None:
            exclusive_group = target_group.add_mutually_exclusive_group(required=item.required)
            exclusive_groups[group_key] = exclusive_group
        exclusive_group.add_argument(*item.flags, **kwargs)


def build_validated_create_payload(
    spec: CreateCommandSpec,
    *,
    args: argparse.Namespace,
    context: CliContext,
) -> dict[str, Any]:
    payload = spec.payload_builder(args, context)
    try:
        validated = spec.validation_model.model_validate(payload)
    except ValidationError as exc:
        raise CliError(_format_create_validation_error(spec, exc)) from exc
    return validated.model_dump(mode="json", exclude_none=True)


def format_create_request_error(resource_label: str, status_code: int, detail: Any) -> str:
    cleaned_detail = _normalize_detail_text(detail)
    if status_code in {400, 422}:
        if cleaned_detail:
            return f"Could not create {resource_label} proposal.\n{cleaned_detail}"
        return f"Could not create {resource_label} proposal."
    return (
        f"Could not create {resource_label} proposal.\n"
        f"HTTP {status_code}: {cleaned_detail or 'unexpected error'}"
    )


def _parse_decimal_amount(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise argparse.ArgumentTypeError("must be a decimal amount like 1234.56")
    try:
        Decimal(normalized)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("must be a decimal amount like 1234.56") from exc
    return normalized


def _build_entries_payload(args: argparse.Namespace, _context: CliContext) -> dict[str, Any]:
    return {
        "kind": args.kind,
        "date": args.date,
        "name": args.name,
        "amount_minor": args.amount_minor,
        "currency_code": args.currency_code,
        "from_entity": args.from_entity,
        "to_entity": args.to_entity,
        "tags": list(args.tags or []),
        "markdown_notes": args.markdown_notes,
    }


def _build_accounts_payload(args: argparse.Namespace, _context: CliContext) -> dict[str, Any]:
    return {
        "name": args.name,
        "currency_code": args.currency_code,
        "markdown_body": args.markdown_body,
        "is_active": args.is_active,
    }


def _build_snapshots_payload(args: argparse.Namespace, context: CliContext) -> dict[str, Any]:
    return {
        "account_id": resolve_account_id(context, account_id=args.account_id),
        "snapshot_at": args.snapshot_at,
        "balance": args.balance,
        "note": args.note,
    }


def _build_groups_payload(args: argparse.Namespace, _context: CliContext) -> dict[str, Any]:
    return {
        "name": args.name,
        "group_type": args.group_type,
    }


def _build_entities_payload(args: argparse.Namespace, _context: CliContext) -> dict[str, Any]:
    return {
        "name": args.name,
        "category": args.category,
    }


def _build_tags_payload(args: argparse.Namespace, _context: CliContext) -> dict[str, Any]:
    return {
        "name": args.name,
        "type": args.type,
    }


def _format_create_validation_error(spec: CreateCommandSpec, exc: ValidationError) -> str:
    lines = [f"Invalid {spec.resource_label} create arguments."]
    for error in exc.errors(include_url=False):
        path = _format_error_path(error.get("loc", ()), spec.field_flag_map)
        message = str(error.get("msg", "invalid value")).strip()
        if path:
            lines.append(f"- {path}: {message}")
        else:
            lines.append(f"- {message}")
    return "\n".join(lines)


def _format_error_path(location: tuple[Any, ...], field_flag_map: dict[str, str]) -> str | None:
    if not location:
        return None
    first = location[0]
    if isinstance(first, str):
        return field_flag_map.get(first, first)
    return str(first)


def _normalize_detail_text(detail: Any) -> str:
    if isinstance(detail, str):
        return _clean_pydantic_text(detail)
    if isinstance(detail, list):
        lines = []
        for item in detail:
            if isinstance(item, dict):
                location = ".".join(str(part) for part in item.get("loc", ()))
                message = str(item.get("msg", "invalid value")).strip()
                lines.append(f"- {location}: {message}" if location else f"- {message}")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)
    if isinstance(detail, dict):
        return "\n".join(f"- {key}: {value}" for key, value in detail.items())
    return str(detail).strip()


def _clean_pydantic_text(message: str) -> str:
    normalized_lines = []
    for raw_line in message.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if _PYDANTIC_LINK_PATTERN.search(stripped):
            continue
        if _PYDANTIC_HEADER_PATTERN.match(stripped):
            continue
        cleaned = _PYDANTIC_METADATA_PATTERN.sub("", stripped)
        normalized_lines.append(cleaned)
    return "\n".join(normalized_lines).strip()


ENTRY_CREATE_SPEC = CreateCommandSpec(
    command_name="entries",
    resource_label="entry",
    change_type="create_entry",
    help_text="Create an entry proposal in the current thread.",
    description=(
        "Create an entry proposal in the current thread.\n\n"
        "Required fields:\n"
        "  --kind, --date, --name, --amount-minor, --from-entity, --to-entity\n"
        "Optional fields:\n"
        "  --currency-code, repeated --tag, --markdown-notes"
    ),
    epilog=(
        "Examples:\n"
        "  bh entries create --kind EXPENSE --date 2026-03-15 --name \"Farm Boy\" \\\n"
        "    --amount-minor 1234 --from-entity Checking --to-entity \"Farm Boy\" --tag grocery\n"
        "\n"
        "--amount-minor uses integer minor units, for example 1234 means 12.34.\n"
        "--date must use YYYY-MM-DD."
    ),
    validation_model=CreateEntryPayload,
    payload_builder=_build_entries_payload,
    fields=(
        CreateFieldSpec(
            flags=("--kind",),
            payload_field="kind",
            required=True,
            argument_kwargs={
                "choices": ("EXPENSE", "INCOME", "TRANSFER"),
                "type": str.upper,
                "help": "Entry kind. Choices: EXPENSE, INCOME, TRANSFER.",
            },
        ),
        CreateFieldSpec(
            flags=("--date",),
            payload_field="date",
            required=True,
            argument_kwargs={"help": "Entry date in YYYY-MM-DD format."},
        ),
        CreateFieldSpec(
            flags=("--name",),
            payload_field="name",
            required=True,
            argument_kwargs={"help": "Human-readable entry name."},
        ),
        CreateFieldSpec(
            flags=("--amount-minor",),
            payload_field="amount_minor",
            required=True,
            argument_kwargs={"type": int, "help": "Integer minor units, for example 1234 for 12.34."},
        ),
        CreateFieldSpec(
            flags=("--from-entity",),
            payload_field="from_entity",
            required=True,
            argument_kwargs={"help": "Source entity name."},
        ),
        CreateFieldSpec(
            flags=("--to-entity",),
            payload_field="to_entity",
            required=True,
            argument_kwargs={"help": "Destination entity name."},
        ),
        CreateFieldSpec(
            flags=("--currency-code",),
            payload_field="currency_code",
            argument_kwargs={
                "type": str.upper,
                "help": "Optional 3-letter currency code. Defaults to runtime settings when omitted.",
            },
        ),
        CreateFieldSpec(
            flags=("--tag",),
            payload_field="tags",
            argument_kwargs={
                "dest": "tags",
                "action": "append",
                "default": None,
                "metavar": "TAG",
                "help": "Tag name. Repeat for multiple tags.",
            },
        ),
        CreateFieldSpec(
            flags=("--markdown-notes",),
            payload_field="markdown_notes",
            argument_kwargs={"help": "Optional markdown notes stored with the proposal."},
        ),
    ),
)


ACCOUNT_CREATE_SPEC = CreateCommandSpec(
    command_name="accounts",
    resource_label="account",
    change_type="create_account",
    help_text="Create an account proposal in the current thread.",
    description=(
        "Create an account proposal in the current thread.\n\n"
        "Required fields:\n"
        "  --name, --currency-code\n"
        "Optional fields:\n"
        "  --markdown-body, --is-active, --inactive"
    ),
    epilog=(
        "Example:\n"
        "  bh accounts create --name \"Wealthsimple Cash\" --currency-code CAD --inactive\n"
        "\n"
        "--currency-code must use a 3-letter code such as CAD or USD."
    ),
    validation_model=CreateAccountPayload,
    payload_builder=_build_accounts_payload,
    parser_defaults={"is_active": True},
    fields=(
        CreateFieldSpec(
            flags=("--name",),
            payload_field="name",
            required=True,
            argument_kwargs={"help": "Account display name."},
        ),
        CreateFieldSpec(
            flags=("--currency-code",),
            payload_field="currency_code",
            required=True,
            argument_kwargs={"type": str.upper, "help": "3-letter currency code such as CAD or USD."},
        ),
        CreateFieldSpec(
            flags=("--markdown-body",),
            payload_field="markdown_body",
            argument_kwargs={"help": "Optional markdown description for the account."},
        ),
        CreateFieldSpec(
            flags=("--is-active",),
            payload_field="is_active",
            exclusive_group="is_active",
            argument_kwargs={"dest": "is_active", "action": "store_const", "const": True, "help": "Mark the account as active."},
        ),
        CreateFieldSpec(
            flags=("--inactive",),
            payload_field="is_active",
            exclusive_group="is_active",
            argument_kwargs={"dest": "is_active", "action": "store_const", "const": False, "help": "Mark the account as inactive."},
        ),
    ),
)


SNAPSHOT_CREATE_SPEC = CreateCommandSpec(
    command_name="snapshots",
    resource_label="snapshot",
    change_type="create_snapshot",
    help_text="Create a snapshot proposal in the current thread.",
    description=(
        "Create a snapshot proposal in the current thread.\n\n"
        "Required fields:\n"
        "  --account-id, --snapshot-at, --balance\n"
        "Optional fields:\n"
        "  --note"
    ),
    epilog=(
        "Example:\n"
        "  bh snapshots create --account-id 1a2b3c4d --snapshot-at 2026-03-15 --balance 1234.56 --note \"statement balance\"\n"
        "\n"
        "--account-id accepts a full id or a unique short id prefix.\n"
        "--snapshot-at must use YYYY-MM-DD.\n"
        "--balance uses a decimal amount such as 1234.56."
    ),
    validation_model=ProposeCreateSnapshotArgs,
    payload_builder=_build_snapshots_payload,
    fields=(
        CreateFieldSpec(
            flags=("--account-id",),
            payload_field="account_id",
            required=True,
            argument_kwargs={"help": "Account id or unique short id prefix."},
        ),
        CreateFieldSpec(
            flags=("--snapshot-at",),
            payload_field="snapshot_at",
            required=True,
            argument_kwargs={"help": "Snapshot date in YYYY-MM-DD format."},
        ),
        CreateFieldSpec(
            flags=("--balance",),
            payload_field="balance",
            required=True,
            argument_kwargs={"type": _parse_decimal_amount, "help": "Decimal balance amount such as 1234.56."},
        ),
        CreateFieldSpec(
            flags=("--note",),
            payload_field="note",
            argument_kwargs={"help": "Optional note for the snapshot."},
        ),
    ),
)


GROUP_CREATE_SPEC = CreateCommandSpec(
    command_name="groups",
    resource_label="group",
    change_type="create_group",
    help_text="Create a group proposal in the current thread.",
    description=(
        "Create a group proposal in the current thread.\n\n"
        "Required fields:\n"
        "  --name, --group-type"
    ),
    epilog=(
        "Example:\n"
        "  bh groups create --name \"Monthly Bills\" --group-type BUNDLE\n"
        "\n"
        "--group-type choices: BUNDLE, SPLIT, RECURRING."
    ),
    validation_model=CreateGroupPayload,
    payload_builder=_build_groups_payload,
    fields=(
        CreateFieldSpec(
            flags=("--name",),
            payload_field="name",
            required=True,
            argument_kwargs={"help": "Group display name."},
        ),
        CreateFieldSpec(
            flags=("--group-type",),
            payload_field="group_type",
            required=True,
            argument_kwargs={
                "choices": ("BUNDLE", "SPLIT", "RECURRING"),
                "type": str.upper,
                "help": "Group type. Choices: BUNDLE, SPLIT, RECURRING.",
            },
        ),
    ),
)


ENTITY_CREATE_SPEC = CreateCommandSpec(
    command_name="entities",
    resource_label="entity",
    change_type="create_entity",
    help_text="Create an entity proposal in the current thread.",
    description=(
        "Create an entity proposal in the current thread.\n\n"
        "Required fields:\n"
        "  --name\n"
        "Optional fields:\n"
        "  --category"
    ),
    epilog=(
        "Example:\n"
        "  bh entities create --name \"Farm Boy\" --category expense"
    ),
    validation_model=CreateEntityPayload,
    payload_builder=_build_entities_payload,
    fields=(
        CreateFieldSpec(
            flags=("--name",),
            payload_field="name",
            required=True,
            argument_kwargs={"help": "Entity display name."},
        ),
        CreateFieldSpec(
            flags=("--category",),
            payload_field="category",
            argument_kwargs={"help": "Optional entity category."},
        ),
    ),
)


TAG_CREATE_SPEC = CreateCommandSpec(
    command_name="tags",
    resource_label="tag",
    change_type="create_tag",
    help_text="Create a tag proposal in the current thread.",
    description=(
        "Create a tag proposal in the current thread.\n\n"
        "Required fields:\n"
        "  --name\n"
        "Optional fields:\n"
        "  --type"
    ),
    epilog=(
        "Example:\n"
        "  bh tags create --name grocery --type expense"
    ),
    validation_model=CreateTagPayload,
    payload_builder=_build_tags_payload,
    fields=(
        CreateFieldSpec(
            flags=("--name",),
            payload_field="name",
            required=True,
            argument_kwargs={"help": "Tag name."},
        ),
        CreateFieldSpec(
            flags=("--type",),
            payload_field="type",
            argument_kwargs={"help": "Optional tag type/category."},
        ),
    ),
)


CREATE_COMMAND_SPECS: dict[str, CreateCommandSpec] = {
    "entries": ENTRY_CREATE_SPEC,
    "accounts": ACCOUNT_CREATE_SPEC,
    "snapshots": SNAPSHOT_CREATE_SPEC,
    "groups": GROUP_CREATE_SPEC,
    "entities": ENTITY_CREATE_SPEC,
    "tags": TAG_CREATE_SPEC,
}

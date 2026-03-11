from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from backend.enums_agent import AgentChangeType
from backend.models_finance import AccountSnapshot
from backend.services.account_snapshots import get_account_snapshot, list_account_snapshots
from backend.services.agent.change_contracts.catalog import (
    ProposeCreateSnapshotArgs,
    ProposeDeleteSnapshotArgs,
)
from backend.services.agent.proposals.common import create_change_item, proposal_result
from backend.services.agent.read_tools.common import get_account_by_id_for_tool_context
from backend.services.agent.tool_results import error_result
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult


def _major_to_minor(value: Decimal) -> int:
    return int((value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _snapshot_record(snapshot: AccountSnapshot) -> dict[str, object]:
    return {
        "id": snapshot.id,
        "snapshot_at": snapshot.snapshot_at.isoformat(),
        "balance_minor": snapshot.balance_minor,
        "note": snapshot.note,
        "created_at": snapshot.created_at.isoformat(),
    }


def _adjacent_snapshot_records(
    snapshots: list[AccountSnapshot],
    *,
    current_snapshot_id: str | None = None,
    current_snapshot_at: str | None = None,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    ordered = sorted(snapshots, key=lambda snapshot: (snapshot.snapshot_at, snapshot.created_at))
    for index, snapshot in enumerate(ordered):
        if current_snapshot_id is not None and snapshot.id == current_snapshot_id:
            previous_snapshot = ordered[index - 1] if index > 0 else None
            next_snapshot = ordered[index + 1] if index + 1 < len(ordered) else None
            return (
                _snapshot_record(previous_snapshot) if previous_snapshot else None,
                _snapshot_record(next_snapshot) if next_snapshot else None,
            )

    if current_snapshot_at is None:
        return None, None

    target_date = datetime.fromisoformat(f"{current_snapshot_at}T00:00:00").date()
    previous_snapshot = None
    next_snapshot = None
    for snapshot in ordered:
        if snapshot.snapshot_at < target_date:
            previous_snapshot = snapshot
            continue
        if snapshot.snapshot_at > target_date:
            next_snapshot = snapshot
            break
    return (
        _snapshot_record(previous_snapshot) if previous_snapshot else None,
        _snapshot_record(next_snapshot) if next_snapshot else None,
    )


def propose_create_snapshot(context: ToolContext, args: ProposeCreateSnapshotArgs) -> ToolExecutionResult:
    account = get_account_by_id_for_tool_context(context, args.account_id)
    if account is None:
        return error_result("account not found", details={"account_id": args.account_id})

    balance_minor = _major_to_minor(args.balance)
    note = args.note.strip() if isinstance(args.note, str) and args.note.strip() else None
    payload = {
        "account_id": account.id,
        "account_name": account.name,
        "currency_code": account.currency_code,
        "snapshot_at": args.snapshot_at.isoformat(),
        "balance_minor": balance_minor,
        "note": note,
    }
    item = create_change_item(
        context,
        change_type=AgentChangeType.CREATE_SNAPSHOT,
        payload=payload,
        rationale_text="Agent proposed recording an account balance snapshot.",
    )
    return proposal_result("proposed snapshot creation", preview=payload, item=item)


def propose_delete_snapshot(context: ToolContext, args: ProposeDeleteSnapshotArgs) -> ToolExecutionResult:
    account = get_account_by_id_for_tool_context(context, args.account_id)
    if account is None:
        return error_result("account not found", details={"account_id": args.account_id})

    snapshot = get_account_snapshot(context.db, account_id=account.id, snapshot_id=args.snapshot_id)
    if snapshot is None:
        return error_result(
            "snapshot not found",
            details={"account_id": account.id, "snapshot_id": args.snapshot_id},
        )

    snapshots = list_account_snapshots(context.db, account_id=account.id)
    previous_snapshot, next_snapshot = _adjacent_snapshot_records(
        snapshots,
        current_snapshot_id=snapshot.id,
    )
    impact_preview = {
        "snapshot_count": len(snapshots),
        "previous_snapshot": previous_snapshot,
        "next_snapshot": next_snapshot,
    }
    payload = {
        "account_id": account.id,
        "account_name": account.name,
        "currency_code": account.currency_code,
        "snapshot_id": snapshot.id,
        "target": _snapshot_record(snapshot),
        "impact_preview": impact_preview,
    }
    item = create_change_item(
        context,
        change_type=AgentChangeType.DELETE_SNAPSHOT,
        payload=payload,
        rationale_text="Agent proposed deleting an account balance snapshot.",
    )
    preview = {
        "account_id": account.id,
        "account_name": account.name,
        "snapshot_id": snapshot.id,
        "snapshot_at": snapshot.snapshot_at.isoformat(),
        "balance_minor": snapshot.balance_minor,
        "impact_preview": impact_preview,
    }
    return proposal_result("proposed snapshot deletion", preview=preview, item=item)

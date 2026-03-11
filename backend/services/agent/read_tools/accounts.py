from __future__ import annotations

from datetime import date

from backend.services.account_snapshots import list_account_snapshots
from backend.services.agent.read_tools.common import get_account_by_id_for_tool_context
from backend.services.agent.tool_args.read import GetReconciliationArgs, ListSnapshotsArgs
from backend.services.agent.tool_results import error_result, format_lines
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus
from backend.services.finance import build_reconciliation


def list_snapshots(context: ToolContext, args: ListSnapshotsArgs) -> ToolExecutionResult:
    account = get_account_by_id_for_tool_context(context, args.account_id)
    if account is None:
        return error_result("account not found", details={"account_id": args.account_id})

    snapshots = list_account_snapshots(context.db, account_id=account.id)
    records = [
        {
            "snapshot_id": snapshot.id,
            "snapshot_at": snapshot.snapshot_at.isoformat(),
            "balance_minor": snapshot.balance_minor,
            "note": snapshot.note,
            "created_at": snapshot.created_at.isoformat(),
        }
        for snapshot in snapshots[: args.limit]
    ]
    total_available = len(snapshots)
    snapshots_text = (
        "; ".join(
            f"snapshot_id={record['snapshot_id']} date={record['snapshot_at']} "
            f"balance_minor={record['balance_minor']}"
            + (f" note={record['note']}" if record.get("note") else "")
            for record in records
        )
        if records
        else "(none)"
    )
    output_json = {
        "status": "OK",
        "summary": f"returned {len(records)} of {total_available} snapshots for {account.name}",
        "account": {
            "account_id": account.id,
            "name": account.name,
            "currency_code": account.currency_code,
        },
        "returned_count": len(records),
        "total_available": total_available,
        "snapshots": records,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: returned {len(records)} of {total_available} snapshots for {account.name}",
                f"snapshots: {snapshots_text}",
            ]
        ),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )


def get_reconciliation(context: ToolContext, args: GetReconciliationArgs) -> ToolExecutionResult:
    account = get_account_by_id_for_tool_context(context, args.account_id)
    if account is None:
        return error_result("account not found", details={"account_id": args.account_id})

    reconciliation = build_reconciliation(context.db, account, args.as_of or date.today())
    closed_intervals = [interval for interval in reconciliation.intervals if not interval.is_open]
    mismatched_count = sum(1 for interval in closed_intervals if interval.delta_minor != 0)
    open_interval = next((interval for interval in reconciliation.intervals if interval.is_open), None)
    interval_lines = []
    for interval in reconciliation.intervals:
        if interval.is_open:
            interval_lines.append(
                f"open {interval.start_snapshot.snapshot_at} -> {reconciliation.as_of}: "
                f"tracked_change_minor={interval.tracked_change_minor} entries={interval.entry_count}"
            )
            continue
        interval_lines.append(
            f"{interval.start_snapshot.snapshot_at} -> {interval.end_snapshot.snapshot_at if interval.end_snapshot else '-'}: "
            f"tracked_change_minor={interval.tracked_change_minor} "
            f"bank_change_minor={interval.bank_change_minor} delta_minor={interval.delta_minor} "
            f"entries={interval.entry_count}"
        )

    output_json = {
        "status": "OK",
        "summary": (
            f"{len(reconciliation.intervals)} interval(s), "
            f"{mismatched_count} mismatched closed interval(s)"
        ),
        "account": {
            "account_id": account.id,
            "name": account.name,
            "currency_code": account.currency_code,
        },
        "reconciliation": reconciliation.model_dump(mode="json"),
    }
    interval_output_lines = interval_lines if interval_lines else ["(none)"]
    open_summary = (
        f"current_open_tracked_change_minor={open_interval.tracked_change_minor}"
        if open_interval is not None
        else "current_open_tracked_change_minor=(none)"
    )
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: {len(reconciliation.intervals)} interval(s), {mismatched_count} mismatched closed interval(s)",
                open_summary,
                "intervals:",
                *interval_output_lines,
            ]
        ),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )

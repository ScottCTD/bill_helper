# Feature Request: Interval-Based Account Reconciliation

## Summary

Replace the current absolute-balance reconciliation model with an interval-based model that compares tracked entry changes against bank balance changes between consecutive snapshots. This lets users set an opening balance via a snapshot and only track changes going forward, without needing to import historical transactions.

## Problem Statement

The current reconciliation computes:

```
delta = SUM(all entries from epoch to as_of) - latest_snapshot_balance
```

This is only meaningful if the user has imported every transaction since the account's inception. In practice, users start tracking at an arbitrary point by recording a snapshot (their current bank balance), then add entries going forward. The current delta is immediately wrong — it compares a partial ledger total against the full bank balance, producing a meaningless number.

**Example of the broken behavior:**

- User records snapshot: Jan 1, $5,000 (opening bank balance)
- User adds entries in January: -$700 expenses, +$100 income
- Current system says: ledger = -$600, snapshot = $5,000, delta = -$5,600
- This tells the user nothing useful

## Core Concept: Interval Reconciliation

Snapshots divide the account timeline into intervals. For each pair of consecutive snapshots, the meaningful comparison is:

```
bank_change    = end_snapshot - start_snapshot      (what the bank says changed)
tracked_change = SUM(entries in the interval)        (what the user recorded)
delta          = tracked_change - bank_change        (untracked difference)
```

This tells the user: "Between these two checkpoints, you're missing $X of transactions."

**Example of the new behavior:**

- Snapshot A: Jan 1, $5,000
- Snapshot B: Feb 1, $4,200
- Entries between Jan 1 and Feb 1: -$700 expenses, +$100 income = -$600
- Bank change: $4,200 - $5,000 = -$800
- Delta: -$600 - (-$800) = +$200 → "you tracked $200 less spending than the bank shows"

### Credit Cards

The same model applies to credit cards. Snapshots represent the balance owed. If the snapshot goes from $1,200 → $1,800, the bank says the user spent $600 net. Tracked entries in that interval should account for that change.

## Design Decisions

### Intervals

- With N snapshots, produce N intervals:
  - N-1 **closed intervals** between consecutive snapshot pairs
  - 1 **open interval** from the latest snapshot to today (or a requested as_of date)
- Closed intervals have both `bank_change` and `tracked_change`, producing a full delta.
- The open interval only has `tracked_change` (no ending snapshot yet), so delta represents "net tracked activity since last checkpoint" with no bank reference.

### Single Snapshot

- When only one snapshot exists, produce a single open interval from that snapshot to today.
- `tracked_change` = SUM(entries since the snapshot date).
- `bank_change` = null (no second snapshot to compare against).
- `delta` = null (cannot compute without bank reference).
- This still gives the user visibility into what they've tracked since establishing the opening balance.

### Entry Date Boundaries

- An entry on a snapshot's date belongs to the interval **ending** at that snapshot (inclusive end).
- Interval range: `(start_snapshot_date, end_snapshot_date]` — exclusive start, inclusive end.
- The frontend should note this boundary behavior to the user so they understand which interval an entry falls into.

### API Response Shape

The reconciliation endpoint returns the **full interval history** for the account. The frontend is responsible for display logic (e.g., highlighting the latest interval, collapsing older ones).

## Proposed API Contract

### `GET /api/v1/accounts/{account_id}/reconciliation`

Query params:
- `as_of` (optional, date): defaults to today. Controls the end boundary of the open interval.

Response:

```json
{
  "account_id": "...",
  "account_name": "...",
  "currency_code": "CAD",
  "as_of": "2026-03-11",
  "intervals": [
    {
      "start_snapshot": { "id": "...", "snapshot_at": "2026-01-01", "balance_minor": 500000 },
      "end_snapshot": { "id": "...", "snapshot_at": "2026-02-01", "balance_minor": 420000 },
      "is_open": false,
      "tracked_change_minor": -60000,
      "bank_change_minor": -80000,
      "delta_minor": 20000,
      "entry_count": 15
    },
    {
      "start_snapshot": { "id": "...", "snapshot_at": "2026-02-01", "balance_minor": 420000 },
      "end_snapshot": null,
      "is_open": true,
      "tracked_change_minor": -35000,
      "bank_change_minor": null,
      "delta_minor": null,
      "entry_count": 8
    }
  ]
}
```

### Interval Object Fields

| Field | Type | Description |
|---|---|---|
| `start_snapshot` | object | The snapshot at the beginning of the interval |
| `end_snapshot` | object or null | The snapshot at the end (null for open intervals) |
| `is_open` | bool | True if this is the most recent interval with no closing snapshot |
| `tracked_change_minor` | int | SUM of signed entries in (start_date, end_date] |
| `bank_change_minor` | int or null | end_snapshot - start_snapshot balance (null for open) |
| `delta_minor` | int or null | tracked_change - bank_change (null for open) |
| `entry_count` | int | Number of entries in the interval |

## Frontend Redesign

### Page Layout Change

The current `AccountsPage` layout has three top-level sections:

1. `AccountsTableSection` — account list/search table
2. Two-column grid: `ReconciliationSection` (left) + `SnapshotsSection` (right)
3. Modal dialogs for create/edit

**Problem:** Reconciliation and snapshots are contextual to a single account, but they're displayed as separate page-level panels below the table. This is awkward — the user selects an account in the table, then looks below for its reconciliation data.

**New layout:** Move reconciliation and snapshot management into the **account edit modal** (`AccountDialogs.tsx`). The edit modal currently only has basic fields (owner, name, currency, active, notes). It should gain two new sections/tabs:

- **Reconciliation tab** — interval-based reconciliation view
- **Snapshots tab** — snapshot CRUD (create form + history table)

The accounts table page becomes a clean list. All account-specific detail lives in the modal.

### Reconciliation Display Design

The reconciliation tab inside the account modal should display the interval list with clear visual hierarchy:

**Interval list (newest first):**

- Each interval shows: date range, tracked change, bank change, delta
- **Open interval** (latest snapshot → today): highlighted as "current period", shows tracked change only, no delta (since there's no closing snapshot yet)
- **Reconciled intervals** (delta = 0): collapsed/shorthand display — just show the date range with a ✓ checkmark or "Reconciled" badge. No need to expand details for these.
- **Mismatched intervals** (delta ≠ 0): visually highlighted (e.g., warning color). Show full details expanded: tracked change, bank change, and the delta amount prominently. The delta should be clearly labeled (e.g., "+$200 untracked" or "-$150 over-tracked").

**Summary bar at top:**

- Total intervals count
- How many are reconciled vs mismatched
- The open interval's tracked change

**Entry boundary note:**

- A small info tooltip or footnote explaining that entries on a snapshot date belong to the interval ending at that snapshot.

### Affected Frontend Modules

- `frontend/src/pages/AccountsPage.tsx` — remove the two-column reconciliation/snapshot grid; page becomes just the table + dialogs
- `frontend/src/features/accounts/AccountDialogs.tsx` — expand the edit dialog to include reconciliation and snapshot tabs
- `frontend/src/features/accounts/ReconciliationSection.tsx` — rewrite for interval list display with reconciled/mismatch styling
- `frontend/src/features/accounts/SnapshotsSection.tsx` — move into the modal context (may need minor prop adjustments)
- `frontend/src/features/accounts/useAccountsPageModel.ts` — reconciliation and snapshot queries move to be modal-driven (fetched when modal opens for an account, not when a table row is selected)
- `frontend/src/lib/api.ts` — update reconciliation response types for interval model

## Agent Tooling

The bill assistant agent currently has account CRUD tools (`list_accounts`, `propose_create_account`, etc.) but **no snapshot or reconciliation tools**. The agent should be able to help users manage snapshots and understand their reconciliation status.

### New Agent Tools

All tools follow the existing pattern: handler function + Pydantic args model + registration in the tool catalog.

#### Read Tools (register in `catalog_read.py`, implement in `read_tools/`)

**`list_snapshots`**
- Args: `account_id` (required), `limit` (optional, default 20)
- Behavior: List snapshots for an account, newest first. Uses `list_account_snapshots()` from `backend/services/account_snapshots.py`.
- Returns: Snapshot list with id, date, balance, note, created_at.

**`get_reconciliation`**
- Args: `account_id` (required), `as_of` (optional date, defaults to today)
- Behavior: Compute interval-based reconciliation for the account. Uses the new `build_reconciliation()` logic from `backend/services/finance.py`.
- Returns: Full interval list with tracked/bank changes and deltas. Should format the output as a human-readable summary highlighting mismatched intervals.

#### Proposal Tools (register in `catalog_proposals.py`, implement in `proposals/`)

**`propose_create_snapshot`**
- Args: `account_id`, `snapshot_at` (date), `balance` (in major currency units — the agent should think in dollars, not cents), `note` (optional)
- Behavior: Create a proposal to add a snapshot. The handler converts major→minor units before persisting.
- Typical agent workflow: user says "my bank balance is $4,200 as of today", agent calls this tool.

**`propose_delete_snapshot`**
- Args: `account_id`, `snapshot_id`
- Behavior: Create a proposal to delete a snapshot.
- Typical agent workflow: user says "remove the January snapshot", agent lists snapshots first, then proposes deletion.

### Proposal Review Modal Design

Snapshot proposals follow the existing review card pattern (header → rationale → diff → editor) with type-specific context panels.

**Create Snapshot Review Card:**

- **Editable fields:** Account name (read-only), snapshot date (date picker), balance (major units input), note (text).
- **Context panel:** Read-only section below the editor showing the account's **nearby snapshots** — the snapshot immediately before and after the proposed date, if they exist. This lets the user eyeball whether the balance progression makes sense (e.g., "previous snapshot was $5,000 on Jan 1, you're adding $4,200 on Feb 1 — that looks reasonable") and spot duplicate dates.
- **Diff preview:** Standard `+ date: 2026-02-01`, `+ balance: $4,200.00`, `+ note: ...` lines.

**Delete Snapshot Review Card:**

- **Snapshot details:** Read-only display of the snapshot being deleted (date, balance, note).
- **Impact panel:** Explains the reconciliation consequence:
  - If the snapshot sits between two others: "Deleting the Feb 1 snapshot will merge intervals [Jan 1 → Feb 1] and [Feb 1 → Mar 1] into a single interval [Jan 1 → Mar 1]."
  - If it's the most recent snapshot: "Deleting this will make [previous snapshot] the new baseline for the open interval."
  - If it's the only snapshot: Warning — "This is the only snapshot for this account. Deleting it removes the opening balance anchor; reconciliation will have no reference point."
- **Standard delete confirmation** checkbox/button.

**Frontend modules:**

- `ReviewCatalogEditors.tsx` — add `ReviewSnapshotEditor` for create proposals (editable fields + nearby-snapshot context).
- `ReviewActiveItemCard.tsx` — add snapshot delete impact rendering in the delete confirmation section.
- `diff/core.ts` — add snapshot field labels (`snapshot_at` → "date", `balance_minor` → "balance") and display order.
- Context data (nearby snapshots, interval impact) should be fetched by the review controller when a snapshot proposal is the active item, using the existing `list_snapshots` and `get_reconciliation` endpoints.

### Agent System Prompt Update

The agent's system prompt or context assembly (`backend/services/agent/message_history.py`) should be updated to mention that the agent can:

- Record bank balance snapshots for accounts
- Check reconciliation status and explain interval deltas
- Help the user identify which periods have untracked transactions

### Tool Args Location

- New args models in `backend/services/agent/tool_args/read.py` (`ListSnapshotsArgs`, `GetReconciliationArgs`)
- New proposal payloads in `backend/services/agent/change_contracts/catalog.py` (`SnapshotCreatePayload`, `SnapshotDeletePayload`)

## Affected Backend Modules

- `backend/services/finance.py` — replace `compute_ledger_balance` + `build_reconciliation` with interval-based logic
- `backend/schemas_finance.py` — new `ReconciliationIntervalRead` schema, update `ReconciliationRead`
- `backend/routers/accounts.py` — update reconciliation endpoint response
- `backend/services/agent/read_tools/` — new snapshot list and reconciliation read tools
- `backend/services/agent/proposals/catalog.py` — new snapshot create/delete proposal tools
- `backend/services/agent/tool_runtime_support/catalog_read.py` — register new read tools
- `backend/services/agent/tool_runtime_support/catalog_proposals.py` — register new proposal tools
- `backend/services/agent/tool_args/read.py` — new args models
- `backend/services/agent/change_contracts/catalog.py` — new snapshot payloads
- `backend/services/agent/message_history.py` — update agent context to mention snapshot/reconciliation capabilities
- `backend/tests/` — update reconciliation math tests, add agent tool tests

## Dashboard

- `backend/services/finance.py` — `list_dashboard_reconciliation_accounts` depends on the old reconciliation shape and will need updating to work with the interval model (or it can compute a simplified summary for dashboard display).

## Migration Notes

- This is a **compute-only change** — no database schema changes needed. Snapshots and entries are stored the same way; only the reconciliation query logic changes.
- The old `ReconciliationRead` response shape changes, so frontend must be updated in lockstep.
- Existing tests for `test_reconciliation_math` need rewriting for the interval model.
- The frontend layout change (moving sections into the modal) can be done as a preparatory step before the reconciliation logic changes, or in lockstep.

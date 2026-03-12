# Feature Map: Account Reconciliation and Snapshots

This doc is the fast path for understanding account management UX, snapshot checkpointing, and reconciliation math.

## Scope

- `GET /api/v1/accounts`
- `POST /api/v1/accounts`
- `PATCH /api/v1/accounts/{account_id}`
- `DELETE /api/v1/accounts/{account_id}`
- `POST /api/v1/accounts/{account_id}/snapshots`
- `GET /api/v1/accounts/{account_id}/snapshots`
- `DELETE /api/v1/accounts/{account_id}/snapshots/{snapshot_id}`
- `GET /api/v1/accounts/{account_id}/reconciliation`
- frontend account workspace in `frontend/src/pages/AccountsPage.tsx`

## Current Frontend Behavior

- Accounts are displayed in a table workspace (search + row selection + double-click row editing + row-level delete action).
- Accounts are entity-root records; each account id is also the backing entity id.
- Account creation is handled by the icon-only `+` action, which opens a modal.
- Account edits are handled by double-clicking a table row, which opens the shared edit modal.
- Account deletion starts from a subdued row-level delete action and is finalized in a confirmation dialog.
- Account metadata now excludes legacy `institution` and `type`; creation still captures owner/name/currency/notes while the edit modal trims the editable fields to name/currency/notes/active state.
- Account create/edit modals include optional markdown notes (`markdown_body`) for richer account-level context.
- The account edit modal is a fixed-height untabbed workspace: compact details stay at the top, the left column scrolls reconciliation plus snapshot history, and the right column holds the snapshot-create form.
- Snapshot creation and deletion happen inside the account modal; each saved snapshot row exposes its own delete action with confirmation.
- The reconciliation section shows newest-first intervals, highlights the open interval separately, compresses reconciled intervals, and expands mismatched intervals.

Delete semantics:

- deleting an account removes the shared account/entity root
- account snapshots are deleted
- linked ledger entries keep their denormalized `from` / `to` text, but account/entity FK references are cleared and the UI shows missing-entity markers

## Reconciliation Semantics

Reconciliation is computed server-side in `backend/services/finance.py` as interval history.

- Snapshots partition the timeline into `(start_snapshot_date, end_snapshot_date]` intervals.
- Closed intervals compare:
  - `bank_change_minor = end_snapshot.balance_minor - start_snapshot.balance_minor`
  - `tracked_change_minor = SUM(account-linked entry effects in the interval)`
  - `delta_minor = tracked_change_minor - bank_change_minor`
- The most recent snapshot always produces one open interval from that snapshot to `as_of`.
- The open interval exposes tracked activity only; it has no bank change or delta because there is no closing checkpoint yet.
- Entries that occur on a snapshot date belong to the interval ending at that snapshot.
- Account-linked entry effects are resolved from the account entity root first:
  - `from_entity_id == account.id` subtracts `amount_minor`
  - `to_entity_id == account.id` adds `amount_minor`
  - legacy rows that only set `account_id == account.id` fall back to entry-kind signing (`INCOME` positive, other kinds negative)

The `as_of` date still defaults to the server's current day when the query parameter is omitted.

## Backend Modules

- `backend/routers/accounts.py`: account create/update/delete plus snapshot/reconciliation routes.
- `backend/services/account_snapshots.py`: shared snapshot create/list/delete persistence workflows.
- `backend/services/agent/message_history.py`: current-user account context assembly for agent system prompt (includes account notes).
- `backend/services/accounts.py`: shared account/entity-root create, update, and delete behavior.
- `backend/services/finance.py`: interval reconciliation builders plus dashboard reconciliation summaries.
- `backend/schemas_finance.py`: `Account*`, `Snapshot*`, `ReconciliationIntervalRead`, and `ReconciliationRead` contracts.

## Frontend Modules

- `frontend/src/pages/AccountsPage.tsx`: thin page orchestrator for accounts workspace composition.
- `frontend/src/features/accounts/useAccountsPageModel.ts`: query/mutation state, derived selection/filter state, and form orchestration.
- `frontend/src/features/accounts/AccountsTableSection.tsx`: account table/search/selection UI.
- `frontend/src/features/accounts/ReconciliationSection.tsx`: interval list UI inside the account modal.
- `frontend/src/features/accounts/SnapshotCreatePanel.tsx`: compact snapshot-create form inside the account modal.
- `frontend/src/features/accounts/SnapshotHistoryTable.tsx`: snapshot history table inside the account modal.
- `frontend/src/features/accounts/AccountDialogs.tsx`: create/edit dialog UI.
- `frontend/src/components/DeleteConfirmDialog.tsx`: shared destructive confirmation dialog primitive.
- `frontend/src/lib/api.ts`: account/snapshot/reconciliation client methods.
- `frontend/src/lib/queryKeys.ts`: account query keys (`accounts`, `snapshots`, `reconciliation`).
- `frontend/src/lib/queryInvalidation.ts`: `invalidateAccountReadModels` after account/snapshot writes.
- `frontend/src/pages/AccountsPage.test.tsx`: integration tests for create-account, snapshot create/delete, and delete-account flows.

## Operational Notes and Constraints

- Create-account default currency is sourced from runtime settings (`GET /api/v1/settings`), then uppercased.
- Snapshot balance input is entered in major units in the UI, then converted to minor units before API submit.
- Snapshot list ordering is newest checkpoint first (`snapshot_at desc`, then `created_at desc`).
- Deleting a snapshot only removes that checkpoint; reconciliation immediately rebuilds its interval history around the remaining checkpoints.
- Snapshots are intended as bank checkpoints, not derived balances; the user must add them manually.

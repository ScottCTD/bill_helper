# Feature Map: Account Reconciliation and Snapshots

This doc is the fast path for understanding account management UX, snapshot checkpointing, and reconciliation math.

## Scope

- `GET /api/v1/accounts`
- `POST /api/v1/accounts`
- `PATCH /api/v1/accounts/{account_id}`
- `DELETE /api/v1/accounts/{account_id}`
- `POST /api/v1/accounts/{account_id}/snapshots`
- `GET /api/v1/accounts/{account_id}/snapshots`
- `GET /api/v1/accounts/{account_id}/reconciliation`
- frontend account workspace in `frontend/src/pages/AccountsPage.tsx`

## Current Frontend Behavior

- Accounts are displayed in a table workspace (search + row selection + row-level edit/delete actions).
- Accounts are entity-root records; each account id is also the backing entity id.
- Account creation is handled by the icon-only `+` action, which opens a modal.
- Account edits are handled by the `Edit` button in each row, which opens a modal.
- Account deletion starts from a subdued row-level delete action and is finalized in a confirmation dialog.
- Account metadata now excludes legacy `institution` and `type`; dialogs focus on owner/name/currency/notes/active state.
- Account create/edit modals include optional markdown notes (`markdown_body`) for richer account-level context.
- Snapshot and reconciliation panels are bound to the currently selected table row.
- Snapshot creation is append-only in the UI (no snapshot edit/delete controls).
- Reconciliation and snapshot panels include plain-language term definitions directly in the page so users can understand fields without leaving the workflow.

Delete semantics:

- deleting an account removes the shared account/entity root
- account snapshots are deleted
- linked ledger entries keep their denormalized `from` / `to` text, but account/entity FK references are cleared and the UI shows missing-entity markers

## Reconciliation Semantics

Reconciliation is computed server-side in `backend/services/finance.py`:

1. `ledger_balance_minor`: sum of account entries up to `as_of` (`INCOME` positive, `EXPENSE` negative).
2. `snapshot_balance_minor`: latest snapshot where `snapshot_at <= as_of`.
3. `delta_minor = ledger_balance_minor - snapshot_balance_minor` when a snapshot exists; otherwise `null`.

The as-of date defaults to the server's current day when the query parameter is omitted.

## Backend Modules

- `backend/routers/accounts.py`: account create/update/delete plus snapshot/reconciliation routes.
- `backend/services/agent/message_history.py`: current-user account context assembly for agent system prompt (includes account notes).
- `backend/services/accounts.py`: shared account/entity-root create, update, and delete behavior.
- `backend/services/finance.py`: ledger aggregation + latest-snapshot lookup.
- `backend/schemas.py`: `Account*`, `Snapshot*`, and `ReconciliationRead` contracts.

## Frontend Modules

- `frontend/src/pages/AccountsPage.tsx`: thin page orchestrator for accounts workspace composition.
- `frontend/src/features/accounts/useAccountsPageModel.ts`: query/mutation state, derived selection/filter state, and form orchestration.
- `frontend/src/features/accounts/AccountsTableSection.tsx`: account table/search/selection UI.
- `frontend/src/features/accounts/ReconciliationSection.tsx`: reconciliation summary UI.
- `frontend/src/features/accounts/SnapshotsSection.tsx`: snapshot create/history UI.
- `frontend/src/features/accounts/AccountDialogs.tsx`: create/edit dialog UI.
- `frontend/src/components/DeleteConfirmDialog.tsx`: shared destructive confirmation dialog primitive.
- `frontend/src/lib/api.ts`: account/snapshot/reconciliation client methods.
- `frontend/src/lib/queryKeys.ts`: account query keys (`accounts`, `snapshots`, `reconciliation`).
- `frontend/src/lib/queryInvalidation.ts`: `invalidateAccountReadModels` after account/snapshot writes.
- `frontend/src/pages/AccountsPage.test.tsx`: integration tests for create-account, create-snapshot, and delete-account flows.

## Operational Notes and Constraints

- Create-account default currency is sourced from runtime settings (`GET /api/v1/settings`), then uppercased.
- Snapshot balance input is entered in major units in the UI, then converted to minor units before API submit.
- Snapshot list ordering is newest checkpoint first (`snapshot_at desc`, then `created_at desc`).
- Snapshots are intended as bank checkpoints, not derived balances; the user must add them manually.

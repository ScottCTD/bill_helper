# Entry Entity Label Repair And Agent Selector Fix

Date: 2026-03-09

## Summary

This fix closed a fatal entry-edit regression and an agent-review regression around `Entry.from_entity` / `Entry.to_entity`.

Visible symptoms:

- editing an existing entry could keep `from_entity_id` / `to_entity_id` intact while writing `from_entity` / `to_entity` to `NULL`
- transfer rows could therefore display blank counterparties even though the linked entities still existed
- the agent could detect the broken rows and propose repairs, but approval failed because the proposal selector carried `null` `from_entity` / `to_entity`

The work included both code fixes and a one-time local data repair for the three corrupted Saving Account transfer rows.

## Root cause

| Area | Finding | Impact |
|---|---|---|
| Entry PATCH route | `backend/routers/entries.py` normalized entity fields using `from` / `to` keys instead of `from_entity` / `to_entity` | Existing-entry edits could persist valid linked IDs with null denormalized labels |
| Agent selector generation | `backend/services/agent/entry_references.py` built selectors directly from raw entry labels | Corrupted rows produced selectors with `from_entity=None` and `to_entity=None` |
| Agent change contract | `EntrySelectorPayload` requires non-null strings for `from_entity` / `to_entity` | Approval of those repair proposals failed before `entry_id`-based targeting could apply the patch |

## Durable fixes

### 1. Correct entry PATCH normalization

`backend/routers/entries.py` now resolves and writes the right keys:

- `from_entity_id` ↔ `from_entity`
- `to_entity_id` ↔ `to_entity`

Durable rule after this fix:

- if the client sends an entity ID with a null label, the backend fills the canonical label from the linked entity before persisting the entry

### 2. Make agent entry references resilient

`backend/services/agent/entry_references.py` now falls back to the linked entity relationship name when the denormalized label is missing.

That keeps agent list/read/selector behavior stable for already-corrupted rows and matches the intended invariant:

- live link present → usable name available

### 3. Make agent approval tolerate legacy broken selectors

`backend/services/agent/change_contracts.py` now drops an incomplete `selector` during normalization when:

- `entry_id` is present, and
- the selector is incomplete or contains null text fields

That preserves strict selector validation for selector-only targeting, while allowing `entry_id`-based updates to approve and apply.

## Data repair

After the code fix landed, the local SQLite DB was repaired for the three known corrupted rows:

- `29dd97b5-6bf5-46db-b3ac-0231c48cf44f`
- `7da85120-e3f9-4491-8d3f-11ba5aca0c6c`
- `e7238f66-7f5f-48b5-84c5-e8eb101ec631`

Repair action:

- populate `from_entity` from `from_entity_ref.name` when `from_entity_id` existed and the label was null
- populate `to_entity` from `to_entity_ref.name` when `to_entity_id` existed and the label was null

Post-repair verification showed `0` remaining rows in the bad state:

- `from_entity_id IS NOT NULL AND from_entity IS NULL`, or
- `to_entity_id IS NOT NULL AND to_entity IS NULL`

## Tests added

### Backend regression coverage

- `backend/tests/test_entries.py::test_update_entry_resolves_entity_labels_from_ids`
  - proves existing-entry PATCH requests preserve canonical labels when IDs are supplied
- `backend/tests/test_agent.py::test_approve_update_entry_drops_invalid_selector_when_entry_id_present`
  - proves approval succeeds for an `entry_id`-targeted update even if a legacy selector payload contains null entity labels

## Validation run

- `uv run python -m py_compile backend/routers/entries.py backend/services/agent/change_contracts.py backend/services/agent/entry_references.py backend/tests/test_entries.py backend/tests/test_agent.py`
- `uv run pytest backend/tests/test_entries.py -q`
- `uv run pytest backend/tests/test_agent.py -q -k 'update_entry'`
- `uv run python scripts/check_docs_sync.py`

All passed after the fixes.

## Prevention notes

- Treat `from_entity` / `to_entity` as denormalized label snapshots, not as optional throwaway fields when an ID is present.
- When an ID is available, backend normalization must restore the canonical label before write.
- Agent approval should not require a selector when a stable `entry_id` already exists.
- The dangerous corruption state to watch for is: live entity ID present, denormalized label missing.

## Files changed

- `backend/routers/entries.py`
- `backend/services/agent/change_contracts.py`
- `backend/services/agent/entry_references.py`
- `backend/tests/test_entries.py`
- `backend/tests/test_agent.py`

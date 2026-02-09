# ADR 0001: Remove Entry Status From Ledger Entries

- Status: accepted
- Date: 2026-02-09
- Deciders: Bill Helper maintainers

## Context

`entries.status` was originally used to represent review state (`CONFIRMED` / `PENDING_REVIEW`).
Review workflow is now modeled by agent review tables (`agent_change_items`, `agent_review_actions`), and pending items are no longer inserted into `entries` before approval.

Keeping `entries.status` caused duplication and stale UI/API surface area.

## Decision

- Remove `entries.status` from ORM, schemas, routers, serializers, and frontend entry types/UI.
- Remove entry-status filters/columns from entry screens.
- Keep review status only in agent change-item domain.
- Apply migration `0009_remove_entry_status`.

## Consequences

- Entry payloads are simpler and less ambiguous.
- Legacy references to entry status must be updated in docs/tests.
- Agent review state remains explicit and isolated to review tables.

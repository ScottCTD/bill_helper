# ADR 0005: Filter-Group-Based Dashboard Classification

- Status: accepted
- Date: 2026-03-10
- Deciders: Bill Helper maintainers

## Context

The dashboard previously hard-coded one analytics split: `daily` vs `non-daily` tags.
That model was too narrow for ordinary budgeting questions such as fixed vs discretionary spend, transfer visibility, and untagged cleanup. It also forced analytics behavior to live inside dashboard code instead of in a reusable user-visible definition.

## Decision

- Introduce first-class principal-owned `filter_groups` persistence with recursive include/exclude rules.
- Provision built-in default groups per user: `day_to_day`, `one_time`, `fixed`, `transfers`, and `untagged`.
- Keep filter-group rules editable while preserving default group identities and names.
- Make dashboard expense analytics consume saved filter groups for month totals, daily series, monthly trend series, largest-expense labeling, and projections.
- Keep internal account-to-account transfers excluded from dashboard analytics and expose `is_internal_transfer` as an explicit rule field for filter-group evaluation.

## Consequences

- Analytics classification is now user-visible, durable, and reusable instead of being a dashboard-local special case.
- Default groups can overlap with custom groups, so summed filter-group shares may exceed `100%`.
- The rule model is intentionally narrow in v1 (`entry_kind`, tags, `is_internal_transfer`, nested `AND`/`OR`) but extensible without changing the user-facing concept.
- `0002-dashboard-cad-analytics-and-tag-segmentation.md` is superseded for classification behavior, but CAD-scoped runtime currency selection remains in effect.

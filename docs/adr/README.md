# Architecture Decision Records (ADR)

Use ADRs for durable technical decisions that affect architecture, data contracts, or team workflow.

## Current ADRs

- `0001-remove-entry-status.md`: removed ledger-level entry status and kept review state in agent change items instead.
- `0002-dashboard-cad-analytics-and-tag-segmentation.md`: fixed dashboard analytics to CAD-scoped reporting with tag-based daily segmentation.
- `0003-xdg-shared-config-and-data.md`: moved default config and runtime data to shared XDG locations.
- `0004-entity-root-account-subtype.md`: made `Account` a shared-primary-key `Entity` subtype and standardized delete semantics around that model.
- `0005-filter-group-analytics.md`: replaced dashboard-local daily/non-daily tagging with saved filter-group analytics classification.

## Naming

- `NNNN-short-title.md` (zero-padded index)
- example: `0001-remove-entry-status.md`

## Status Values

- `accepted`
- `superseded`
- `deprecated`

## Template

```md
# ADR NNNN: <Title>

- Status: accepted
- Date: YYYY-MM-DD
- Deciders: <names or team>

## Context

## Decision

## Consequences
```

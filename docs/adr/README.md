# Architecture Decision Records (ADR)

Use ADRs for durable technical decisions that affect architecture, data contracts, or team workflow.

## Current ADRs

- `0001-remove_entry_status.md`: removed ledger-level entry status and kept review state in agent change items instead.
- `0002-dashboard_cad_analytics_and_tag_segmentation.md`: fixed dashboard analytics to CAD-scoped reporting with tag-based daily segmentation.
- `0003-xdg_shared_config_and_data.md`: moved default config and runtime data to shared XDG locations.
- `0004-entity_root_account_subtype.md`: made `Account` a shared-primary-key `Entity` subtype and standardized delete semantics around that model.
- `0005-filter_group_analytics.md`: replaced dashboard-local daily/non-daily tagging with saved filter-group analytics classification.
- `0006-llm-oriented-design-policy.md`: adopted the non-iOS LLM-oriented design baseline and documented the temporary iOS defer.

## Naming

- `NNNN-short_title.md` (zero-padded index)
- example: `0001-remove_entry_status.md`

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

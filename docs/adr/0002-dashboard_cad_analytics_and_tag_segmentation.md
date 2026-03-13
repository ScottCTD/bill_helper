# ADR 0002: CAD-Scoped Dashboard With Tag-Based Daily Segmentation

- Status: superseded
- Date: 2026-02-09
- Deciders: Bill Helper maintainers

Superseded by `0005-filter_group_analytics.md`.

## Context

The prior dashboard was a single long page with limited static charts and mixed-currency aggregation.
Users needed interactive analytics with clearer sections, plus explicit daily-vs-non-daily spending insights.

## Decision

- Redesign dashboard into interactive tabs (overview/daily/breakdowns/insights).
- Use Recharts for interactive bar/area/pie visualizations.
- Scope dashboard analytics to CAD for current iteration.
- Segment expenses by tags:
  - `daily` => daily
  - `non-daily` / `non_daily` / `nondaily` => non-daily override
- Add current-month projection based on spend-to-date pace.

## Consequences

- Dashboard behavior is deterministic and easier to reason about for current seed data.
- Non-CAD dashboard analytics are intentionally excluded and can be added later behind a separate decision.
- Tag conventions now affect analytics quality and should be documented/communicated to users.

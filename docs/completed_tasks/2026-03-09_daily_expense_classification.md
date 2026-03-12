# Feature Request: Daily Expense Classification and Filter Groups

## Summary

Introduce a user-facing classification system for financial entries that supports consistent spending views, better dashboard segmentation, and user-defined analytics slices. The feature should organize entries into a small set of meaningful default categories while allowing those groupings to be customized over time.

The primary objective is to make expense and income trends easier to understand without requiring users to manually reconstruct the same views for every analysis workflow.

## Problem Statement

Current entry tagging can capture detail, but it does not yet produce a clear higher-level classification model for everyday analysis. As a result:

- day-to-day spending is hard to separate from one-time or fixed costs
- transfer activity can distort expense and income summaries
- untagged entries are not surfaced as a distinct cleanup category
- dashboards cannot consistently answer common questions such as "How much did I spend day-to-day this month?" or "What portion of spending is fixed versus discretionary?"

The system needs a structured way to define reusable filters that can power analytics without forcing users to create custom dashboards or bespoke chart logic.

## Core Concept: Filter Groups

Filter groups are the core concept of this feature.

A filter group is a user-visible, reusable saved definition that selects entries based on logical conditions. Instead of treating analytics categories as hard-coded buckets, the product should treat them as named filter groups that can be used consistently across dashboard and reporting surfaces.

Each filter group should include:

- a name
- an intended meaning for users (description)
- a logical matching rule
- inclusion and exclusion conditions

This feature should be framed around filter groups first, and classification categories second. In other words, `day-to-day`, `one-time`, `fixed`, `transfers`, and `untagged` are default filter groups, not special one-off exceptions

## Goals

- Define clear default classification groups for common financial analysis.
- Enable consistent daily, monthly, projected, and insight-based reporting using those groups.
- Let users review and adjust the classification rules behind each group.
- Support future dashboard expansion without redesigning the classification model.
- Keep the feature focused on standardized analytics views rather than custom dashboard building.

## Non-Goals

- user-designed charts, plots, or dashboard layouts
- advanced handling of special grouped-transfer accounting cases in the first version
- a fully open-ended analytics builder for arbitrary visualizations
- solving every transfer edge case before basic classification is usable

## Logical Filtering Model

Filter groups should use a structured logical filtering model similar to Notion-style filters.

The product should support:

- conditions combined with `AND`
- conditions combined with `OR`
- negation or exclusion logic
- grouped conditions so users can build nested filter logic
- plain-language editing so users can understand why a filter group matches an entry

At a product level, a filter group should be able to express rules like:

- kind is expense
- tag contains any of a selected set
- tag contains none of a selected set
- this condition group and that condition group must both match
- at least one of several alternative condition groups must match

The initial release should at minimum support logical filtering over:

- entry kind
- tags present
- tags excluded

The overall model should be extensible to additional entry fields over time without changing the user-facing concept of a filter group.

## Default Filter Group Definitions

The feature should support the following default high-level groups:

- `day-to-day`: recurring everyday spending such as groceries, coffee, dining, transportation, personal care, pharmacy, and similar routine purchases
- `one-time`: irregular or exceptional purchases such as electronics, furniture, or unusually large orders
- `fixed`: predictable recurring obligations such as rent, insurance, phone plans, and similar baseline expenses
- `transfers`: external money movement that should remain visible but separated from ordinary spending analysis
- `untagged`: entries that do not match the intended classification groups and need review

These defaults should provide an immediately useful baseline while remaining editable by the user.

The initial default definitions should be:

- `day-to-day`
  Covers ordinary expense activity associated with routine living costs such as grocery, dining out, coffee or snacks, transportation, personal care, pharmacy, alcohol or bars, fitness, entertainment, subscriptions, home, and pets. This group should exclude entries marked as one-time and should exclude internal transfers.
- `one-time`
  Covers exceptional or irregular expense activity identified as one-time spending. This group should exclude internal transfers.
- `fixed`
  Covers recurring baseline obligations such as housing, utilities, internet or mobile, insurance, interest expense, taxes, and debt payment. This group should exclude internal transfers.
- `transfers`
  Covers external transfer-like activity such as e-transfer and cash withdrawal. This group should exclude internal transfers.
- `untagged`
  Covers entries that do not match the intended primary classification groups and therefore need review.

The default groups should be designed to produce useful out-of-the-box reporting with minimal overlap in primary expense analysis, while still allowing users to refine the rules later.

## Key User Needs

- View spending broken down into meaningful categories without manual cleanup each time.
- Separate ordinary spending from fixed costs and one-time purchases.
- Keep transfers visible without letting them overwhelm actual spending patterns.
- Detect untagged or poorly classified entries that need follow-up.
- Create additional custom groups when default categories are not enough.
- Adjust existing group definitions as tagging habits evolve.

## Functional Requirements

### 1. Default Filter Groups

The product should provide a predefined set of filter groups for:

- day-to-day
- one-time
- fixed
- transfers
- untagged

These groups should be presented as first-class analytics dimensions, not as ad hoc one-off views.

### 2. Editable Group Definitions

Users should be able to:

- inspect how each filter group is defined
- edit the rules for default groups
- create new custom filter groups
- rename custom groups
- update group logic as their categorization needs change

The system should treat these groups as reusable saved definitions rather than temporary filters.

### 3. Entry Classification Coverage

Filter groups should be able to classify entries based on meaningful entry properties. At minimum, the classification model should support:

- entry kind conditions
- tag inclusion conditions
- tag exclusion conditions
- nested logical groups using `AND` and `OR`
- exclusion logic needed to keep primary analytics categories clean

The model should be general enough to support richer filtering logic over time without changing the core user-facing concept.

### 4. Filter Group Management Rules

The product should define clear behavior for how filter groups are used and maintained:

- default filter groups exist out of the box
- users can edit default group rules
- users can create additional custom groups
- custom groups can overlap with other groups
- default primary analytics groups should aim to be understandable and low-overlap
- users should be able to inspect why a group includes or excludes a given class of entries

### 5. Analytics Surfaces Powered by Filter Groups

Filter groups should support the following analytics use cases:

- monthly expenses by filter group
- daily expenses by filter group
- income by filter group
- projected expenses by filter group
- insights grouped by dimensions such as tags, source entities, destination entities, and saved filter groups

The feature should make these views consistent across analytics surfaces.

### 6. Transfer Visibility Without Misleading Aggregation

Transfers should remain visible as a separate category, but the product should avoid presenting them as ordinary spending by default. The feature should recognize that transfer-like activity can otherwise inflate both expense and income views.

For the initial version, special treatment of grouped or reimbursed transfer scenarios does not need to be fully solved, but the system should leave room for manual tagging and later refinement.

### 7. Untagged Cleanup Workflow

The feature should explicitly surface entries that do not fall into the intended filter groups. This gives users a practical way to find classification gaps and improve tag quality over time.

## Product Constraints

- The feature should prioritize clarity and usefulness over exhaustive financial modeling.
- Default groups should work out of the box for common household budgeting patterns.
- The model should remain user-customizable.
- The first release should avoid coupling classification to fully customizable dashboard creation.
- Internal transfers should not be treated the same way as ordinary expenses or external transfers.
- The feature should describe filter behavior in user terms rather than exposing low-level implementation details.

## Open Questions

- Should untagged only mean "matches no group," or specifically "matches no intended primary classification group"?
- What user experience should exist for reviewing and resolving entries that appear misclassified?
- How much transfer detail should appear in summary views versus deeper drill-down views?
- What default terminology should be used in the UI for these groups to feel intuitive and durable?

## Success Criteria

- Users can view day-to-day, one-time, fixed, transfer, and untagged activity as distinct analytics segments.
- Users can adjust the classification logic without needing engineering support.
- Dashboard-style summaries become easier to interpret because transfer activity and exceptional purchases no longer blur ordinary spending.
- Untagged entries become visible enough to support routine cleanup.
- The feature provides a stable foundation for future analytics expansion.
- Users can define or edit filter groups using logical conditions without needing custom dashboards.

## Scope of Work

To complete this feature request, the product work should cover:

- defining filter groups as a first-class user-facing concept
- defining the logical filter language and its supported operators
- defining the default classification groups and their intended semantics
- defining the rule model for saved filter groups
- deciding how default and custom groups are managed by the user
- deciding which analytics surfaces consume filter groups in the first release
- defining how transfer-related activity is presented in summaries
- defining how untagged entries are surfaced and reviewed
- documenting guardrails and exclusions for the initial release

## Raw Thoughts

I want to categorize expenses into the following "big" categories based on taggings:

1. day-to-day: like groceries, coffee, dining, transportation, personal care, pharmacy, etc
   - Note that this should also includes tagged transfers if any, see below.
2. one-time: like electronics, furniture, big Amazon orders, etc
3. fixed: like rent, insurance, phone plan, etc
4. transfers: all external transfers
5. untagged: all expenses that are not tagged with any of the above categories

For transfers, this become quite a bit more complicated.

- For SPLIT group, we know that we only spent our own money, but we paid for everyone, and everyone paid us back. However, if we aggregate this, then we're bloating both of our actual expenses and incomes.
- There are even more complicated cases like delayed rent refund, and pay back rent to my roommate, I paid the rent to my landlord, and my roommate paid me back, etc.
- But if we can tag transfers manually, then they also be informative as well. Like tagging a transfer to my friend as actually the dinner he paid in whole.
- For now in those aggregated stats calculation, let's not consider special treatment of entry groups for now.

But how to identify day-to-day expenses?
- I guess the best choice is to simply have good tags for one-time expenses.
- In this way, the day-to-day expenses are simply expenses that match the following tags but not one-time expenses.
  Tags: grocery, dining_out, coffee_snacks, transportation, personal_care, pharmacy, alcohol_bars, fitness, entertainment, subscriptions, home, pets
- And fixed expenses: "housing, utilities, internet_mobile, insurance, interest_expense, taxes, debt_payment"
- Transfers are simply "e-transfer" and "cash_withdrawal"
- Note that "internal_transfer" is excluded from ALL of the above.
- We should also allow users to edit tags for day-to-day expenses, one-time expenses, fixed expenses, and transfers.
- A more general way here is to have another level of tags, namely tag groups. Or even futher generalized, a filter group. A filter group provides filtering entries based on all fields of entries. I personally prefer the filter group approach, because it's more flexible and easier to extend in the future.

The overarching goal is to provide good and customizible dashboards for me to view my stats.
Some basic stats:
- Monthly expenses based on filter groups (pre-defined are day-to-day, one-time, fixed, transfers)
- Daily expenses based on filter groups
- Income based on filter groups
- Projected expenses based on filter groups
- Insights of data (by tags, by from entity, by to entity - basically by filter groups)
- Maybe more I can't think of now.

The user should be able to add custom filter groups, and edit the filter groups.
For the user should NOT be allowed to have customized plots/charts/dashboards. This should be implemented AFTER the agent workspace task is completed and we can leverage the agent to generate code to generate the plots/charts/dashboards.

Filter groups might look like:
```
name: Day-to-Day
match:
  kind: [EXPENSE]
  tags_any: [grocery, dining_out, coffee_snacks, transportation,
             personal_care, pharmacy, alcohol_bars, fitness,
             entertainment, subscriptions, home, pets]
  tags_none: [one_time, internal_transfer]

name: One-Time
match:
  kind: [EXPENSE]
  tags_any: [one_time]
  tags_none: [internal_transfer]

name: Fixed
match:
  kind: [EXPENSE]
  tags_any: [housing, utilities, internet_mobile, insurance,
             interest_expense, taxes, debt_payment]
  tags_none: [internal_transfer]

name: Transfers
match:
  kind: [EXPENSE, INCOME, TRANSFER]
  tags_any: [e_transfer, cash_withdrawal]
  tags_none: [internal_transfer]
```
The rules for filter groups would then be based on logic operators like Notion style filtering. For e.g.: kind = ... AND tag contains ... AND tag not contains ... AND ...

# Plan: Daily Expense Classification & Filter Groups

Please use this as the source of truth if there's any conflicts between this and the above feature request and raw thoughts.

## Problem

The current dashboard classifies expenses using a primitive `daily` / `non-daily` tag check. This doesn't answer real questions like "how much did I spend day-to-day vs one-time vs fixed?" and forces manual mental grouping. The task proposes **filter groups** — reusable, user-editable saved filter definitions that classify entries into meaningful analytics buckets.

## Agreed Decisions (from discussion)

| Topic | Decision |
|---|---|
| Storage | DB table, per-user (defaults seeded per user at creation) |
| "Unclassified" | Remainder bucket: entries with no tags OR entries not matching any filter group |
| Multi-match | Allowed — an entry can appear in multiple filter groups |
| Transfers group | Includes any entry tagged `e_transfer`/`cash_withdrawal` regardless of kind |
| Legacy daily/non-daily | Removed entirely (tags + dashboard logic + schema fields) |
| Evaluation | On-the-fly at query time (no materialized cache) |
| Filter model v1 | Flat: `kind_in`, `tags_any`, `tags_none` — nested AND/OR deferred |
| Scope | Full: backend model + API + dashboard overhaul + filter group management UI |
| Month navigation | Scrollable timeline (no manual month picker) |
| Dashboard style | Tabbed views, creative/elegant Recharts charts, human-readable insights |

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  filter_groups table (per-user, JSON rule column)    │
│  ─────────────────────────────────────────────────   │
│  id | owner_user_id | name | slug | description |    │
│  is_default | position | rule (JSON) | timestamps    │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │  FilterGroupService          │
        │  • evaluate(entries, groups) │
        │  • classify_entry(entry)     │
        │  • seed_defaults(user)       │
        └──────────────┬──────────────┘
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
  Routers:          Services:         Frontend:
  /filter-groups    Dashboard          FilterGroupsPage
  /dashboard        (refactored)       DashboardPage (redesigned)
```

## Todos

### Phase 1: Backend Data Model & Seed

**1.1 — Create `filter_groups` table + Alembic migration**
- New model `FilterGroup` in `models_finance.py`:
  - `id` (UUID PK)
  - `owner_user_id` (FK → users, indexed)
  - `name` (str, e.g. "Day-to-Day")
  - `slug` (str, unique per user, e.g. "day-to-day")
  - `description` (text, user-facing explanation)
  - `is_default` (bool, marks system-provided groups)
  - `position` (int, display ordering)
  - `rule` (JSON column, stores the filter definition)
  - `created_at`, `updated_at` (timestamps)
- UniqueConstraint on `(owner_user_id, slug)`
- Rule JSON schema v1:
  ```json
  {
    "version": 1,
    "kind_in": ["EXPENSE"],
    "tags_any": ["grocery", "dining_out", ...],
    "tags_none": ["one_time", "internal_transfer"]
  }
  ```
- The special "unclassified" group has `rule: {"version": 1, "mode": "unclassified"}` — computed dynamically as remainder.
- Alembic migration: `alembic revision --autogenerate -m "add_filter_groups"`

**1.2 — Seed default filter groups per user**
- Add `seed_default_filter_groups(db, user_id)` to `scripts/seed_defaults.py` or a new `backend/services/filter_groups.py`.
- Call during user creation flow so new users get defaults automatically.
- 5 default groups with `is_default=True`:

| slug | name | kind_in | tags_any | tags_none |
|---|---|---|---|---|
| `day-to-day` | Day-to-Day | [EXPENSE] | grocery, dining_out, coffee_snacks, transportation, personal_care, pharmacy, alcohol_bars, fitness, entertainment, subscriptions, home, pets | one_time, internal_transfer |
| `one-time` | One-Time | [EXPENSE] | one_time | internal_transfer |
| `fixed` | Fixed | [EXPENSE] | housing, utilities, internet_mobile, insurance, interest_expense, taxes, debt_payment | internal_transfer |
| `transfers` | Transfers | [EXPENSE, INCOME, TRANSFER] | e_transfer, cash_withdrawal | internal_transfer |
| `unclassified` | Unclassified | — | — | — | (mode: "unclassified") |

**1.3 — Remove legacy `daily` / `non-daily` tags and logic**
- Remove `daily` from `DEFAULT_TAGS` in `seed_defaults.py` (it's not currently there — confirm and ensure it doesn't creep in).
- Remove `DASHBOARD_DAILY_TAG_NAME`, `DASHBOARD_NON_DAILY_TAG_NAMES` constants from `finance.py`.
- Remove `_entry_has_daily_tag()` function.
- Remove `daily_expense_total_minor`, `non_daily_expense_total_minor`, `daily_expense_minor`, `non_daily_expense_minor`, `average_daily_expense_minor`, `median_daily_expense_minor`, `daily_spending_days`, `is_daily` from all schemas.
- This is a breaking change — dashboard frontend will be updated in Phase 3.

### Phase 2: Backend Service & API

**2.1 — FilterGroup evaluation service (`backend/services/filter_groups.py`)**
- `list_filter_groups(db, user_id) → list[FilterGroup]` — ordered by position.
- `get_filter_group(db, user_id, group_id) → FilterGroup`.
- `create_filter_group(db, user_id, payload) → FilterGroup`.
- `update_filter_group(db, user_id, group_id, payload) → FilterGroup`.
- `delete_filter_group(db, user_id, group_id)` — prevent deleting `is_default` groups? Or allow with warning? (Allow — user can always re-seed.)
- `evaluate_filter_group(rule: dict, entry: Entry) → bool` — pure function that checks if an entry matches a rule.
  - For standard rules: `entry.kind in rule.kind_in AND entry has any tag in rule.tags_any AND entry has no tag in rule.tags_none`.
  - For "unclassified": entry has no tags, OR entry doesn't match any other non-unclassified group for that user.
- `classify_entries(db, user_id, entries: list[Entry]) → dict[str, list[Entry]]` — returns `{group_slug: [entries]}`. An entry can appear in multiple groups. Unclassified is computed as remainder.
- `seed_default_filter_groups(db, user_id)` — idempotent, creates defaults if missing.

**2.2 — Filter groups CRUD router (`backend/routers/filter_groups.py`)**
- `GET /filter-groups` — list all for current user.
- `GET /filter-groups/{group_id}` — get one.
- `POST /filter-groups` — create custom group.
- `PATCH /filter-groups/{group_id}` — update name, description, rule, position.
- `DELETE /filter-groups/{group_id}` — delete (soft or hard, TBD).
- Request/response schemas in `schemas_finance.py`:
  - `FilterGroupRead`: id, name, slug, description, is_default, position, rule, created_at, updated_at.
  - `FilterGroupCreate`: name, description, rule.
  - `FilterGroupUpdate`: name?, description?, rule?, position?.
  - `FilterGroupRuleRead`: version, kind_in?, tags_any?, tags_none?, mode?.

**2.3 — Refactor dashboard service to use filter groups**
- Replace `_entry_has_daily_tag` / daily vs non-daily logic with filter group classification.
- New dashboard response shape:
  - `kpis`: total expense, total income, net, per-filter-group expense totals.
  - `filter_group_breakdown`: `[{group_slug, group_name, total_minor, share, entry_count}]`.
  - `daily_spending`: per-date points with per-filter-group breakdown (not just daily/non-daily).
  - `monthly_trend`: per-month points with per-filter-group breakdown + income.
  - `spending_by_tag`, `spending_by_from`, `spending_by_to`: kept as-is.
  - `weekday_spending`: kept.
  - `largest_expenses`: kept, but replace `is_daily` with `filter_groups: [slug]`.
  - `projection`: kept, but projected for each filter group (or at least day-to-day + total).
  - `reconciliation`: kept as-is.
- The API should accept an optional `filter_group_ids` query param to scope analytics to specific groups.
- The dashboard endpoint should return filter group metadata alongside the data so the frontend knows group names/colors.

**2.4 — Dashboard API response schema redesign**
- `DashboardKpisRead`: remove daily/non-daily fields, add `filter_group_totals: list[FilterGroupTotalRead]` where each has `slug, name, total_minor, entry_count`.
- `DashboardDailySpendingPoint`: `date, expense_total_minor, filter_group_totals: list[{slug, total_minor}]`.
- `DashboardMonthlyTrendPoint`: `month, expense_total_minor, income_total_minor, filter_group_totals: list[{slug, total_minor}]`.
- `DashboardLargestExpenseItem`: replace `is_daily` with `filter_groups: list[str]` (slugs).
- New: `DashboardFilterGroupSummary`: `slug, name, description, color, total_minor, share, entry_count` — returned at top level so frontend can render legend/tabs.

### Phase 3: Frontend — Filter Group Management Page

**3.1 — New route: `/filter-groups`**
- Add to `App.tsx` router config with lazy loading.
- Add sidebar navigation item.

**3.2 — FilterGroupsPage component**
- List all filter groups with drag-to-reorder (position field).
- Each group card shows: name, description, rule summary in plain language (e.g., "Expenses tagged with grocery, dining_out, ... but not one_time or internal_transfer").
- Click to edit → dialog/sheet with:
  - Name, description fields.
  - Rule editor: kind selector (checkboxes for EXPENSE/INCOME/TRANSFER), tag inclusion multi-select, tag exclusion multi-select.
  - Preview: show count of matching entries with current rule.
- "Add Custom Group" button → same editor.
- Delete button for non-default groups (confirm dialog).
- Default groups show a badge and can be edited but not deleted (or can be deleted with "Reset to defaults" option).

**3.3 — API client + query keys**
- Add `filterGroups` key namespace to `queryKeys.ts`.
- Add API client functions in a new `lib/api/filterGroups.ts` or extend existing client.
- Invalidation: editing a filter group should invalidate dashboard queries too (since classification changes).

### Phase 4: Frontend — Dashboard Redesign

**4.1 — Remove legacy daily/non-daily UI**
- Remove all references to `daily_expense_total_minor`, `non_daily_expense_total_minor`, `is_daily`, etc.
- Remove the "Daily vs Non-daily" pie chart.
- Remove the "Daily Spend" tab in its current form.

**4.2 — Scrollable month timeline navigation**
- Replace `<input type="month">` with a horizontal scrollable timeline.
- Shows month labels (e.g., "Jan", "Feb", "Mar 2026") as clickable chips/pills.
- Current/selected month is highlighted.
- Auto-scrolls to show current month on load.
- Can scroll left to see older months, right for future (up to current month).
- Optionally show mini sparkline bars under each month chip (total expense) for visual context.

**4.3 — Overview tab redesign**
- **KPI row**: Total Expense, Total Income, Net, Day-to-Day total (or primary group).
- **Filter Group Breakdown**: Horizontal stacked bar or donut chart showing expense split by filter group. Each group gets a consistent color. Clicking a segment could filter the view.
- **Monthly Trend**: Stacked area or bar chart (6–12 months) with each filter group as a layer + income line overlay.
- **Projection Card**: Projected monthly total, projected by day-to-day group specifically, days elapsed/remaining.

**4.4 — Spending tab (replaces "Daily Spend")**
- **Daily spending area chart**: Stacked areas by filter group, x-axis = dates in month.
- **Filter group KPIs**: Average daily spend for day-to-day group, median, spending days count.
- **Comparison**: This month vs last month for each filter group (small delta indicators).

**4.5 — Breakdowns tab (enhanced)**
- **By filter group**: Primary visualization — pie/donut or horizontal bars.
- **By tag**: Top tags pie chart (kept, enhanced with filter group color coding).
- **By destination entity**: Top merchants/payees ranked bar chart.
- **By source entity**: Top sources ranked bar chart.

**4.6 — Insights tab (enhanced)**
- **Weekday heatmap or bar chart**: Spending patterns by day of week.
- **Largest expenses table**: With filter group badges instead of daily/non-daily flag.
- **Unclassified entries alert**: If unclassified count > 0, show a prominent card with count and link to review.
- **Reconciliation**: Kept as-is.
- **Yearly view**: Aggregate by year with monthly bars, filter group stacking, YoY comparison.

**4.7 — Color system for filter groups**
- Assign deterministic colors to default groups (consistent across sessions).
- Custom groups get colors from a palette or user-chosen.
- Colors returned from API in `DashboardFilterGroupSummary`.

### Phase 5: Docs & Cleanup

**5.1 — Update documentation**
- `docs/data-model.md`: Add `filter_groups` table documentation.
- `docs/api.md` / `docs/api/*.md`: Document new `/filter-groups` endpoints and dashboard schema changes.
- `backend/docs/*.md`: Update service and router docs.
- `frontend/docs/*.md`: Update dashboard and new page docs.
- `docs/repository-structure.md`: Update if file structure changed.

**5.2 — Update seed scripts**
- Ensure `seed_defaults.py` creates filter groups.
- Remove any `daily`/`non-daily` tag references.

**5.3 — Run verification gates**
- `uv run python -m py_compile` on all touched Python modules.
- `OPENROUTER_API_KEY=test uv run pytest backend/tests -q`.
- `uv run python scripts/check_docs_sync.py`.

**5.4 — Move task doc to completed**
- Move `tasks/2026-03-09_daily_expense_classification.md` → `docs/completed_tasks/`.

## Open Design Decisions (to resolve during implementation)

1. **Filter group colors**: Hardcoded per default group, or derived from slug hash like tags?
2. **Yearly view**: Separate tab or section within Overview/Insights?
3. **"Unclassified" evaluation performance**: For large entry sets, evaluating against ALL other groups to find remainders could be slow. May need optimization if entry count grows beyond ~10k/month.
4. **Filter group rule versioning**: The `version: 1` field in rule JSON allows future migration to nested AND/OR without breaking existing rules.
5. **Drag-to-reorder UX**: Use `@dnd-kit` or similar? Or simple up/down arrows?

## Dependency Graph

```
1.1 (DB model)
 ├→ 1.2 (seed defaults)
 ├→ 1.3 (remove legacy)
 └→ 2.1 (evaluation service)
      ├→ 2.2 (CRUD router)
      ├→ 2.3 (dashboard service refactor)
      │    └→ 2.4 (schema redesign)
      │         └→ 4.1 (remove legacy FE)
      │              ├→ 4.2 (timeline nav)
      │              ├→ 4.3 (overview tab)
      │              ├→ 4.4 (spending tab)
      │              ├→ 4.5 (breakdowns tab)
      │              └→ 4.6 (insights tab)
      └→ 3.1, 3.2, 3.3 (filter group mgmt page)
4.7 (colors) — parallel with any Phase 4 work
5.x (docs/cleanup) — after all implementation
```

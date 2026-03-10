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

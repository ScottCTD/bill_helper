# ADR 0004: Entity-Root Account Subtype

- Status: accepted
- Date: 2026-03-06
- Deciders: scottcui

## Context

Accounts previously lived as standalone rows linked to separate entity rows through `accounts.entity_id`.

That design created three sources of drift:

1. **Duplicated identity state.** Account names and entity names had to stay in sync across create and update flows.
2. **Category-driven semantics.** Dashboard and agent logic inferred "account-ness" from `entities.category = 'account'`, which is weaker than checking whether a real account subtype row exists.
3. **Inconsistent delete behavior.** Direct API routes, property management, and agent apply logic did not share one canonical rule for deleting account-backed entities, generic entities, or tags.

The refactor work also needed account deletion that preserves visible ledger history while removing the account root and its account-only dependents.

## Decision

Model accounts as an entity-root subtype table with a shared primary key:

- `accounts.id` is both the account primary key and a foreign key to `entities.id`
- `accounts.entity_id` is removed
- account names live only on the entity root
- account-ness is determined by membership in `accounts`, not by `entities.category`

Deletion rules are standardized around that model:

- `DELETE /api/v1/accounts/{account_id}` deletes the shared account/entity root, deletes snapshots, clears `entries.account_id`, and detaches `from_entity_id` or `to_entity_id` while preserving denormalized label text
- generic entity routes may not mutate or delete account-backed roots and return `409` instead
- generic entity deletion preserves visible entry labels and nulls the entity foreign keys
- tag deletion always succeeds, clears taxonomy-backed tag type state, and removes `entry_tags` rows through database cascade behavior
- agent proposal and apply flows reuse the same subtype and delete semantics instead of maintaining parallel rules

## Consequences

### Positive

- The data model now matches the domain intent that an account is an entity with additional fields.
- Name synchronization logic between accounts and entities is removed.
- Dashboard analytics and agent tooling use subtype membership for internal-transfer detection, which is more explicit and less error-prone than category inference.
- Account, entity, and tag delete semantics are now consistent across HTTP routes, frontend workflows, and agent apply handlers.

### Negative

- Queries that need account display data must join the account subtype row to its entity root for name lookup.
- Existing databases require a key-rewrite migration so account references move from old standalone account ids to shared entity-root ids.

### Operational Impact

- Migration `0024_entity_root_accounts.py` rewrites account ids and dependent foreign keys in `entries` and `account_snapshots`.
- Public API contracts change: `AccountRead.entity_id` is removed, `EntityRead.is_account` is added, and entry read models include `from_entity_missing` / `to_entity_missing`.
- Frontend account, entries, and properties workspaces now surface delete flows and missing-entity markers based on the new contracts.

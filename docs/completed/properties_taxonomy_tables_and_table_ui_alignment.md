# TODO Proposal: Properties Taxonomies and Table UI Alignment

## Draft Date

- 2026-02-09

## Why This Proposal Exists

The backend now supports taxonomy-based categories (`tag_category`, `entity_category`), but the frontend `Properties` page still renders a top-down list of independent sections and does not expose taxonomy tables directly.

At the same time, table surfaces across the app are visually inconsistent. In `Entries`, the add action is a compact rightmost `+` control, while property tables still use mixed form/table layouts.

## Current Behavior (Baseline)

- `PropertiesPage` stacks `Users`, `Entities`, `Tags`, and `Currencies` vertically.
- `Entities` exposes a `category` column inline, but there is no dedicated category table management.
- `Tags` currently does not expose category management in UI.
- Table header/action alignment differs across pages.
- Filter row layout differs between `Entries` and `Properties` (control sizing, spacing, and action alignment).

## Goals

1. Expose `Tag Categories` and `Entity Categories` as first-class, user-manageable property tables.
2. Replace the current top-down wall of sections with a clearer navigation model.
3. Align table interaction patterns and visual hierarchy with the app’s table standard (including rightmost primary add action style).
4. Align filter layout system between `Entries` and `Properties` so controls feel like one product surface.
5. Keep implementation incremental and compatible with current APIs.

## Non-Goals (V1)

1. No agent review flow changes.
2. No backend schema redesign beyond existing taxonomy APIs.
3. No multi-level arbitrary taxonomy editor UI (only category term CRUD in this iteration).

## Proposed UX Direction

## 1) Information Architecture for `Properties`

Use a two-level structure instead of a long single column:

- Level A: `Core` vs `Taxonomies`
- Level B inside `Core`: `Users`, `Entities`, `Tags`, `Currencies`
- Level B inside `Taxonomies`: `Entity Categories`, `Tag Categories`

Recommended V1 UI mechanism:

- Left rail (or top segmented tabs on mobile) for section switching.
- Single active table view per section.
- Optional search/filter per section in a shared toolbar area.

## 2) Taxonomy Surfaces

### `Entity Categories` table

- columns: `Name`, `Usage` (count of entities assigned), `Actions`
- actions: create, rename

### `Tag Categories` table

- columns: `Name`, `Usage` (count of tags assigned), `Actions`
- actions: create, rename

## 3) Entities and Tags Table Integration

- `Entities` table keeps `Category` column and edit ability.
- `Tags` table gains `Category` column and edit ability.
- Category pickers should be sourced from taxonomy terms (not free-form only), with optional create-on-type behavior if desired.

## 4) Shared Table Pattern Alignment

Adopt one table-shell pattern for `Entries`, `Accounts`, and all `Properties` tables:

- top row: title + optional subtitle
- toolbar row:
  - left: filters/search
  - right: primary add control (compact icon button style, matching entries rightmost action language)
- table body with consistent row density and action button tone
- shared empty/loading/error states

Filter toolbar parity requirements:

- Use one shared layout primitive/class for filter rows across `Entries` and `Properties`.
- Keep consistent control widths for common filter types (`select`, `text input`, compact action button).
- Keep the same vertical rhythm (`label`/`control` spacing, row gap, wrap behavior).
- On desktop, primary add control stays right-aligned; on mobile, it wraps predictably without reordering.
- Avoid mixed legacy (`controls-inline`) and newer (`filter-row`) patterns in the same table surface.

## Affected Files / Modules (Planned)

Frontend:

- `frontend/src/pages/PropertiesPage.tsx`
- `frontend/src/lib/api.ts` (taxonomy API methods)
- `frontend/src/lib/types.ts` (taxonomy types)
- `frontend/src/lib/queryKeys.ts` (taxonomy query keys)
- `frontend/src/lib/queryInvalidation.ts` (taxonomy invalidation rules)
- shared table/toolbar primitives (existing `components/ui/*` and/or new small wrappers)
- styling tokens/classes in `frontend/src/styles.css`

Backend (already available, no required schema change in this proposal):

- `GET /api/v1/taxonomies`
- `GET /api/v1/taxonomies/{taxonomy_key}/terms`
- `POST /api/v1/taxonomies/{taxonomy_key}/terms`
- `PATCH /api/v1/taxonomies/{taxonomy_key}/terms/{term_id}`

## Operational Impact

- More `Properties` page queries due to taxonomy term list/usage rendering.
- Additional invalidations needed when category terms are created/renamed or assignments change.
- No migration required for frontend rollout because taxonomy backend already exists.

## Constraints / Known Limitations

1. Taxonomy term UI in V1 should stay flat list; hierarchical parent-term editing can be deferred.
2. Usage counts are term-level assignment counts; they are not semantic rollups.
3. Currencies can remain read-only placeholder in this iteration.

## Test Plan

Frontend behavior checks:

1. `Properties` navigation switches sections without layout collapse.
2. `Tag Categories` and `Entity Categories` are visible and editable.
3. `Tags` and `Entities` category cells reflect taxonomy assignments correctly.
4. Table toolbars use consistent alignment; add action appears on the right in all applicable sections.
5. `Entries` and `Properties` filter rows use the same layout pattern, sizing rules, and responsive wrap behavior.
6. Mobile layout preserves usable section switching and action access.

Regression checks:

1. Existing `Users`, `Entities`, `Tags`, `Currencies` behaviors remain functional.
2. Entries and Accounts pages are visually unaffected except intended shared table style standardization.

## Acceptance Criteria

1. Users can directly manage `Tag Categories` and `Entity Categories` in `Properties`.
2. `Properties` page no longer feels like one long top-down stack.
3. Table controls follow a consistent pattern across app pages.
4. Primary add affordances are visually consistent and right-aligned where applicable.
5. Filter bars in `Entries` and `Properties` are visually and structurally aligned.

# TODO: Account Markdown Notes Editor

## Objective

Add an account-level markdown editor (similar to entry `markdown_body`) so each account can store rich description/notes.
Also unify frontend create (`+`) and edit interactions to use modal editors consistently, following the entry editor popup interaction model.

## Current Gap

- Entry create/edit already supports a markdown body.
- Account create/edit currently supports structured fields only (`name`, `currency_code`, owner, active status).
- There is no persistent rich-text/markdown field for account context such as account purpose, operational notes, reconciliation reminders, or statement quirks.
- Frontend create/edit UX is inconsistent across domains:
  - entries use popup modal editors
  - accounts use dedicated dialogs
  - properties sections still rely on inline create panels and inline row edit controls

## Proposed Behavior

1. Account create/edit UI includes a markdown editor section for optional notes.
2. Account notes are stored on the account record and returned by account read/list endpoints.
3. Existing accounts without notes remain valid (`null`/empty notes).
4. Notes are editable without impacting reconciliation math or snapshot workflows.
5. Agent system prompt context (`## Current User Context`) includes each current-user account's markdown description.
6. All remaining frontend `+` and `Edit` actions use modal editors (no inline create panel or inline row edit mode).

## Agent Context Requirements

1. Extend `backend/services/agent/message_history.py` current-user context builder to include account markdown notes.
2. Keep markdown structure in serialized context text so headings/lists/checklists/links remain readable by the model.
3. Image handling:
   - minimum: include markdown image references (`![alt](url)` or equivalent) in context text.
   - optional enhancement: if account notes contain image data URLs, evaluate promoting them to multimodal `image_url` parts only when model vision is enabled.
4. Add truncation/size safeguards so large account notes do not overwhelm system-context token budget.

## Frontend Modal Unification Requirements

1. Standardize create/edit interaction pattern for non-entry domains to modal dialogs opened by `+` and `Edit` actions.
2. Replace inline create/edit flows in properties sections (`users`, `entities`, `tags`, taxonomy term sections) with modal-based forms.
3. Keep existing API contracts and mutations; this is a presentation/state-management refactor, not a backend contract change.
4. Preserve existing validation/error states in the modal flow (field-level checks and mutation error messages).
5. Keep keyboard and accessibility behavior consistent with existing dialog primitives (focus trap, escape close, submit/cancel actions).

## Planned Implementation Scope

### Backend

- Data model:
  - add nullable text column on `accounts` for markdown notes (suggested name: `markdown_body` for parity with entries).
- API/schema:
  - include the new field in `AccountCreate`, `AccountUpdate`, and `AccountRead`.
- Router logic:
  - persist notes on create/update in `backend/routers/accounts.py`.
- Migration:
  - add an Alembic migration for the new account markdown column.

### Frontend

- Form state:
  - extend `AccountFormState` with account markdown notes.
- UI:
  - add markdown editor section in account create/edit dialogs (reuse existing markdown editor component used by entries where appropriate).
  - refactor remaining inline create/edit workflows to modal dialogs across frontend property-management surfaces.
  - align modal affordances (`+`, `Edit`, cancel/save) with entry editor UX expectations.
- API client/types:
  - include the new field in account payload/response typing.

## Affected Files/Modules (Expected)

- Backend:
  - `backend/models.py`
  - `backend/schemas.py`
  - `backend/routers/accounts.py`
  - `backend/services/agent/message_history.py`
  - `backend/tests/test_agent.py`
  - migration under `alembic/versions/*`
- Frontend:
  - `frontend/src/features/accounts/types.ts`
  - `frontend/src/features/accounts/useAccountsPageModel.ts`
  - `frontend/src/features/accounts/AccountDialogs.tsx`
  - `frontend/src/pages/PropertiesPage.tsx`
  - `frontend/src/features/properties/usePropertiesPageModel.ts`
  - `frontend/src/features/properties/usePropertiesSectionState.ts`
  - `frontend/src/features/properties/sections/UsersSection.tsx`
  - `frontend/src/features/properties/sections/EntitiesSection.tsx`
  - `frontend/src/features/properties/sections/TagsSection.tsx`
  - `frontend/src/features/properties/sections/TaxonomyTermsSection.tsx`
  - `frontend/src/lib/types.ts`
  - `frontend/src/lib/api.ts`
  - account-related tests
  - properties-page tests

## Operational Impact

- Database schema migration required:
  - `uv run alembic upgrade head`
- Validation checks to run during implementation:
  - `uv run --extra dev pytest`
  - `cd frontend && npm run test`
  - `cd frontend && npm run build`
  - `uv run python scripts/check_docs_sync.py`

## Constraints and Notes

- Notes are optional and should not block account creation/edit.
- Reconciliation and snapshot calculations must remain unchanged.
- Migration should be backwards compatible for existing rows.
- Agent context injection should degrade gracefully when notes are empty, very long, or contain malformed markdown/image links.
- Modal refactor must not change backend payload shapes or mutation semantics.

## Acceptance Criteria

1. User can create an account with markdown notes.
2. User can edit existing account notes.
3. Notes round-trip correctly through API and UI (create, list/read, update).
4. Existing account workflows (search, selection, snapshots, reconciliation) continue working.
5. Agent-run prompt payload includes account markdown description in `## Current User Context`.
6. Frontend `+` and `Edit` actions in properties/account management open modal editors rather than inline edit/create panels.
7. Existing create/update behavior remains unchanged functionally after modal refactor.
8. Tests and docs are updated with no docs-sync failures.

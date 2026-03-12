# 2026-03-12 Entry AI Tag Suggestion

## Status

- Completed

## Summary

Add an AI-assisted tag suggestion action to the entry editor modal's `Tags` row.
The feature should let the user request a fresh tag recommendation for the current
entry draft, replace the current tag selection with the suggested tags, and keep
the result editable before the normal modal save path runs.

This should be a dedicated entry-tagging workflow, not a visible chat thread and
not part of the general agent review/proposal UX.

## Locked Product Decisions

- The AI action lives in the shared entry editor modal, so it applies to both
  create and edit entry flows.
- Running the suggestion replaces the modal's current tag selection.
- Suggested tags must come only from the existing tag catalog. The AI does not
  create new tags.
- Few-shot context uses `1` current draft entry plus up to `9` similar tagged
  entries.
- A blank tagging-model setting disables the feature.
- If the feature is disabled because no tagging model is configured, the UI
  should notify the user instead of silently doing nothing.
- The workflow does not appear in the agent workspace, thread list, or run
  history.
- Button behavior:
  - first click starts the suggestion run
  - click while running interrupts the in-flight run and applies no change
  - after completion or interruption, the button returns to its idle AI state
- Running-state visuals:
  - default running state shows a spinner
  - running plus hover switches to a red stop affordance
- Closing the entry modal terminates the in-flight suggestion workflow and must
  not apply a late result afterward.

## Current-State Findings

- The entry editor modal is implemented in
  `frontend/src/components/EntryEditorModal.tsx` and is reused by:
  - `frontend/src/pages/EntriesPage.tsx`
  - `frontend/src/pages/EntryDetailPage.tsx`
  - `frontend/src/pages/GroupsPage.tsx`
- The tag input itself is a generic reusable component in
  `frontend/src/components/TagMultiSelect.tsx`.
  It is also used for filters, so the AI affordance should be added at the
  entry-editor level, not baked into `TagMultiSelect`.
- Runtime settings currently expose only the general agent model via
  `agent_model` and `available_agent_models`.
  There is no dedicated tagging-model field yet.
- The backend already has a thin direct model-call seam in
  `backend/services/agent/runtime.py`.
  That seam is a better fit for this feature than the full
  thread/message/proposal workflow.
- There is no existing service for "similar entries" in the ledger layer.
  A new focused similarity module is needed.

## Desired UX

### Entry editor

- In the `Tags` row, place an AI button immediately to the right of the tag
  field.
- Idle state:
  - shows the AI icon/button treatment
  - click starts a suggestion request for the current entry draft
- Running state:
  - shows a spinner by default
  - on hover, switches to a red stop icon treatment
  - click interrupts the request
- Completion state:
  - replace the current modal tag selection with the suggested tag list
  - return the button to idle state
- Interrupt state:
  - keep the current tag selection unchanged
  - clear loading state immediately
  - ignore any late response payload

### Disabled configuration behavior

- Add a dedicated settings field labeled `Default tagging model`.
- If that field is blank, the feature is disabled.
- In the entry editor, clicking the AI button while no tagging model is
  configured should show a notification such as:
  `AI tag suggestion is disabled until you set Default tagging model in Settings.`
- Do not fall back to `agent_model` when this field is blank.

### Modal close behavior

- Closing the modal while a suggestion is running must abort the request and
  discard the pending result.
- Do not convert the request into a background job.
- Modal close should not be blocked by the tagging workflow.

## Settings and Configuration Changes

Add a new runtime-settings field for the dedicated tagging model.

Recommended field name:

- backend/runtime field: `entry_tagging_model`
- settings label: `Default tagging model`

Required changes:

- database model: add nullable `entry_tagging_model` to `runtime_settings`
- contracts and schemas:
  - `backend/contracts_settings.py`
  - `backend/schemas_settings.py`
  - `backend/services/runtime_settings_contracts.py`
  - `frontend/src/lib/types.ts`
- runtime settings resolution/view:
  - include the effective value and override metadata
- settings form state and UI:
  - `frontend/src/features/settings/formState.ts`
  - `frontend/src/features/settings/types.ts`
  - `frontend/src/features/settings/SettingsAgentSection.tsx`
- tests for settings contracts and persistence

Validation rule:

- If `entry_tagging_model` is non-empty, it should be validated against
  `available_agent_models` so the feature stays inside the existing enabled
  model catalog.

## Backend Design

### High-level shape

Implement a dedicated entry-tag suggestion API and service stack.

This feature should be implemented as a self-contained vertical slice under the
ledger domain, while reusing only the low-level model transport/configuration
seam that already exists.

Do not:

- create an agent thread
- persist an agent run for this feature
- route this through the proposal/review system
- overload the generic `/agent/threads/...` send-message endpoints

Preferred ownership split:

- router: request/response translation only
- services:
  - similarity selection
  - prompt assembly
  - model invocation
  - response parsing/validation

### Architectural stance

To keep clean architecture intact:

- keep this feature under the entries/runtime-settings surfaces rather than the
  conversational agent surface
- treat it as an inline entry-editing assistant, not as a chat workflow
- reuse the low-level model transport in `backend/services/agent/runtime.py`
  only for provider configuration, retries, and model invocation
- do not couple this feature to:
  - thread creation
  - message history
  - tool schemas
  - proposal review
  - persisted run/event history

Reason:

- the agent thread subsystem is designed for visible conversational workflows
  with persistent history and reviewable change items
- this tagging action is an ephemeral modal-scoped assist
- forcing it through the thread/run model would be the wrong abstraction and
  would spread unrelated agent concerns into the entry-editing path

### Recommended module shape

Recommended backend shape:

- router:
  - `backend/routers/entries.py`
- focused services:
  - `backend/services/entry_similarity.py`
  - `backend/services/entry_tag_suggestions.py`
- optional prompt helper if needed:
  - `backend/services/entry_tag_suggestion_prompt.py`

Responsibilities:

- `entries.py`
  - parse request payload
  - resolve principal/db dependencies
  - map service errors to HTTP responses
- `entry_similarity.py`
  - query candidate entries in-scope for the principal
  - score and rank candidates deterministically
  - return up to `9` few-shot examples
- `entry_tag_suggestions.py`
  - validate runtime configuration
  - load tag catalog and descriptions
  - assemble prompt input payload
  - call the model through the low-level runtime seam
  - parse and validate structured output
  - reject unknown tags

This keeps router ownership limited to HTTP translation and avoids creating a
mixed-responsibility "AI entries" module.

### Suggested API shape

Add a focused route under the entries surface, for example:

- `POST /api/v1/entries/tag-suggestion`

Request payload should contain the current draft entry context, not only an
existing `entry_id`, so the same route works for both create and edit flows.

Suggested request fields:

- `entry_id` optional, for edit mode and self-exclusion
- `kind`
- `occurred_at`
- `name`
- `amount_minor`
- `currency_code`
- `from_entity_id`
- `from_entity`
- `to_entity_id`
- `to_entity`
- `owner_user_id`
- `markdown_body`
- `current_tags`

Suggested response fields:

- `suggested_tags: string[]`

Backend guards:

- if `entry_tagging_model` is blank, reject with a clear client-facing error
- if the configured tagging model is not in `available_agent_models`, reject
  with a clear client-facing error
- only return existing catalog tag names
- if model output contains unknown tags, treat that as an invalid response and
  fail cleanly rather than silently creating tags

### Model invocation approach

Use the existing low-level model transport seam in
`backend/services/agent/runtime.py` rather than building a second provider
integration path.

Implementation guidance:

- call the low-level model function with a dedicated prompt and no tools
- do not reuse the general agent system prompt
- do not construct a fake thread/message/run just to reach the model
- keep the tagging prompt local to this feature

This preserves one canonical provider/retry/configuration path while keeping the
feature's business logic independent from the chat agent runtime.

## Similar Entry Selection Algorithm

Add a dedicated service module for similarity lookup.

Example module split:

- `backend/services/entry_tag_suggestions.py`
- `backend/services/entry_similarity.py`

### Candidate pool

Similarity lookup should use only entries visible to the current principal and
should:

- exclude deleted entries
- exclude the current entry id when editing
- prefer entries that already have at least one tag
- prefer same-kind entries first
- fall back to cross-kind entries only when there are not enough same-kind
  examples

### Scoring signals

Use a simple deterministic heuristic scorer. Do not introduce embeddings or a
vector dependency for this feature.

Recommended signals, ordered by importance:

1. normalized name similarity
2. exact or normalized match on `from` / `to` entities
3. same currency
4. amount proximity
5. markdown-body keyword overlap when notes exist
6. recency as a tie-breaker

Important bias guard:

- do not use the current draft tags as a primary similarity signal
- the user is explicitly invoking this because the current tags may be wrong

### Suggested ranking behavior

- compute a weighted score per candidate
- sort descending by score, then by recency
- return up to `9` examples
- include fewer examples when the corpus is small
- if no useful examples exist, still run the model with the tag catalog and the
  current entry only

### Example heuristic outline

- name:
  - exact normalized match gets the strongest boost
  - substring/token overlap gets a medium boost
- entities:
  - exact same `from_entity_id` or normalized `from_entity` gets a strong boost
  - exact same `to_entity_id` or normalized `to_entity` gets a strong boost
- amount:
  - same rounded amount or near-ratio bucket gets a medium boost
- currency:
  - exact match gets a modest boost
- notes:
  - shared normalized keywords get a low boost

The goal is not perfect semantic matching. The goal is to provide a strong
small-example set without adding infrastructure complexity.

## Prompt Contract

Build a custom tagging prompt for this workflow instead of reusing the generic
agent system prompt.

### Prompt inputs

The prompt should include:

- the current entry draft
- the full current tag catalog
- each tag's description when present
- up to `9` similar tagged entries as few-shot examples
- the current draft tags, if any, as weak context only

### Prompt guidance

The prompt should explicitly tell the model:

- choose the best set of tags from the existing catalog only
- similar entries are examples, not rules
- current draft tags may be incomplete or wrong
- do not overfit to the tags already present on the draft
- do not blindly copy the tags from similar examples
- use tag descriptions when deciding between overlapping tags
- return no tag rather than inventing a weak match

The instruction should encourage careful internal deliberation while returning
only the final structured answer.

### Output format

Prefer a strict structured output format.

Recommended shape:

```json
{
  "suggested_tags": ["grocery", "day_to_day"]
}
```

Implementation requirements:

- parse and validate the response strictly
- normalize names before matching against the catalog
- reject unknown tags
- deduplicate while preserving stable order

## Frontend Implementation Notes

### Placement

Keep the AI affordance in `EntryEditorModal`, not in `TagMultiSelect`.

Reason:

- `TagMultiSelect` is shared with filter UIs
- the AI action depends on entry-draft context and runtime settings
- the modal is the correct seam for cancellation on close

Recommended frontend shape:

- `EntryEditorModal.tsx`
  - owns form state and wires the AI action into the `Tags` row
- dedicated hook, for example `useEntryTagSuggestion`
  - owns request lifecycle and abort state
  - calls the focused entries API
  - applies successful tag replacement back into modal form state

Do not bake modal-specific AI state into the shared tag multiselect component.

### State handling

Extract the request/cancellation logic into a focused hook instead of growing
`EntryEditorModal.tsx` inline even further.

Suggested hook responsibility:

- start suggestion request
- own `AbortController`
- expose idle/running/interrupting state
- apply suggestion result into modal form state
- discard late results after abort or modal close
- raise notifications for disabled config or request failure

### Cancellation model

Cancellation should stay request-scoped and modal-scoped.

Recommended behavior:

- frontend:
  - abort the fetch on second click
  - abort the fetch on modal close/unmount
  - ignore all late responses after abort
- backend:
  - keep the request synchronous from the client's point of view
  - avoid background-job handoff
  - where practical, stop processing when the client disconnects

This is a better fit than introducing a persisted job/run abstraction for a
single inline assist button.

### Visual consistency

Reuse existing app iconography patterns:

- spinner: match the `Loader2` running indicator already used in
  `frontend/src/features/agent/panel/AgentThreadList.tsx`
- stop state: match the destructive stop affordance already used in
  `frontend/src/features/agent/panel/AgentComposer.tsx`

## Failure and Cancellation Rules

- Interrupting the run must not change tags.
- Closing the modal must not apply a late result.
- Request failure must leave tags unchanged and restore the button to idle.
- Unknown-tag output from the model is a failure, not a partial success.
- The feature must not auto-create missing tags as a fallback.

## Non-Goals

- no agent thread creation
- no visible run history for tag suggestions
- no automatic tag creation
- no embedding or vector-search infrastructure
- no change to normal entry-save semantics outside tag replacement in modal
- no separate standalone tagging screen in this work item

## Verification Expectations

When implementing this task, run at minimum:

- `uv run python -m py_compile ...` on touched Python modules
- `OPENROUTER_API_KEY=test uv run pytest backend/tests -q`
- targeted frontend tests for the entry editor and settings form
- `uv run python scripts/check_docs_sync.py`

## Docs To Update During Implementation

The implementation should update the relevant stable docs in the same work item.

Expected doc touch points:

- `docs/api/catalogs-and-settings.md`
- `docs/api/core-ledger.md` if the new route lands under the entries API
- `backend/docs/runtime-and-config.md`
- `frontend/docs/workspaces.md` if the entry editor behavior changes are
  documented there
- `docs/README.md` if a new stable doc is introduced

## Exit Criteria

- Entry editor shows an AI tag-suggestion button for both create and edit flows.
- Blank `Default tagging model` disables execution and produces a clear user
  notification.
- Running state shows spinner by default and stop-on-hover behavior.
- Second click interrupts with no tag change.
- Closing the modal aborts the in-flight workflow and applies no late result.
- Suggestions use only existing tags from the catalog.
- Prompt context includes the current entry, tag descriptions, and up to `9`
  similar tagged examples.
- Similar-entry lookup is implemented as a dedicated deterministic service.
- The feature does not surface in the agent workspace/history.

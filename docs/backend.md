# Backend Documentation

## Stack

- FastAPI
- SQLAlchemy 2.x
- Pydantic v2
- Alembic
- SQLite (local file)
- LiteLLM model-provider routing for chat completions
- PyMuPDF (`pymupdf`) for PDF text extraction (line-trimmed and whitespace-normalized) and per-page rendering in agent message history

## Entry Points

- App factory + ASGI app: `backend/main.py`
- Backend run command: `uv run bill-helper-api`
- Health endpoint: `GET /healthz`

## Configuration (`backend/config.py`)

Settings use prefix `BILL_HELPER_`.

Core app settings:

- `APP_NAME`
- `API_PREFIX` (default `/api/v1`)
- `DATABASE_URL` (default `sqlite:///./.data/bill_helper.db`)
- `CORS_ORIGINS` (default `http://localhost:5173`)
- `CURRENT_USER_NAME` (default `scott`)
- `CURRENT_USER_TIMEZONE` / `BILL_HELPER_CURRENT_USER_TIMEZONE` (default `America/Toronto`)
- `DEFAULT_CURRENCY_CODE` (default `CAD`)
- `DASHBOARD_CURRENCY_CODE` (default `CAD`)

Agent settings:

- `LANGFUSE_PUBLIC_KEY` / `BILL_HELPER_LANGFUSE_PUBLIC_KEY` (optional; enables LiteLLM Langfuse callbacks when both keys are set)
- `LANGFUSE_SECRET_KEY` / `BILL_HELPER_LANGFUSE_SECRET_KEY` (optional; enables LiteLLM Langfuse callbacks when both keys are set)
- `LANGFUSE_HOST` / `BILL_HELPER_LANGFUSE_HOST` (optional; defaults to Langfuse cloud host if unset)
- `AGENT_MODEL` (default `openrouter/moonshotai/kimi-k2.5`)
- `AGENT_MAX_STEPS` (default `100`)
- `AGENT_MAX_IMAGE_SIZE_BYTES` (default `5MB`; per-attachment size limit for image/PDF agent uploads)
- `AGENT_MAX_IMAGES_PER_MESSAGE` (default `4`; max image/PDF uploads per message)
- runtime pricing uses LiteLLM model-cost mapping (`litellm`) and refreshes cost map from LiteLLM source with local fallback

Runtime override behavior:

- `runtime_settings` table stores optional per-field overrides managed by `GET/PATCH /api/v1/settings`, including `user_memory`
- effective runtime settings are resolved as `override -> env default` where applicable
- `user_memory` is an optional DB-only text field used for persistent per-user agent context

Behavior notes:

- app starts even when provider credentials are missing
- only agent message execution is blocked (`503`) when LiteLLM cannot resolve credentials for the configured model target
- LiteLLM resolves provider credentials from environment variables for the configured model (for example `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`)
- when `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are configured, LiteLLM Langfuse callbacks are enabled for success/failure traces (Langfuse is pinned to `<3` because the legacy callback is incompatible with Langfuse v3; to use v3, migrate to `langfuse_otel` and OpenTelemetry)
- credential pre-validation is best-effort; if provider validation is indeterminate, the run proceeds and provider/model errors are surfaced at model-call time
- env settings are cached by `get_settings()` (`lru_cache`)
- runtime behavior consumers use `backend/services/runtime_settings.py` for resolved effective values

## Database Layer (`backend/database.py`)

- shared SQLAlchemy engine/sessionmaker
- SQLite uses `check_same_thread=False`
- request-level session dependency: `get_db()`

## Domain Models (`backend/models.py`)

Core ledger models:

- `Account`, `AccountSnapshot`
- `Entry`, `EntryGroup`, `EntryLink`
- `User`, `Entity`
- `Tag`, `EntryTag`
- `Taxonomy`, `TaxonomyTerm`, `TaxonomyAssignment`

Agent models (review-gated mutation audit system):

- `AgentThread`
- `AgentMessage`
- `AgentMessageAttachment`
- `AgentRun`
- `AgentToolCall`
- `AgentChangeItem`
- `AgentReviewAction`

## Schemas (`backend/schemas.py`)

Existing schemas cover accounts, entries, links, groups, dashboard, users/entities/tags/currencies.
Group read models include:

- `GroupSummaryRead` (derived list row for `GET /groups`)
- `GroupGraphRead` (`nodes` + `edges` for `GET /groups/{group_id}`)

Agent schemas add API contracts for:

- thread list/create/detail
- timeline messages and attachment metadata
- run status, tool call history, and run usage metrics:
  - `input_tokens`
  - `output_tokens`
  - `cache_read_tokens`
  - `cache_write_tokens`
  - `input_cost_usd`
  - `output_cost_usd`
  - `total_cost_usd`
- change item payloads and review actions
- approve/reject request bodies

## Service Layer

Core services:

- `backend/services/entries.py`
- `backend/services/entities.py`
- `backend/services/users.py`
- `backend/services/groups.py`
- `backend/services/finance.py`
  - keeps account reconciliation math
  - now builds tab-oriented dashboard analytics sections:
    - configured-currency monthly KPIs
    - daily vs non-daily spend series (tag-driven)
    - monthly trend rollups
    - from/to/tag breakdowns
    - weekday distribution
    - current-month projection
- `backend/services/serializers.py`
- `backend/services/taxonomy.py`

Agent services:

- `backend/services/agent/runtime.py`
  - executes one run per user message
  - orchestrates bounded tool-calling loop and run lifecycle persistence
  - supports both non-stream execution and SSE execution (`run_existing_agent_run_stream`) for incremental text delivery
  - emits `reasoning_update` SSE events when `send_intermediate_update` tool calls succeed, and when a tool-calling model step includes assistant text that should be treated as the same user-visible progress signal
  - supports manual run interruption (`interrupt_agent_run`) and cooperative stop checks between model/tool steps
  - aggregates model usage metrics across all model calls in a run and persists totals on `agent_runs`
  - passes model observability context (`user`, `session_id=thread.id`, run-level `trace`) on each model request for conversation-level trace grouping
  - delegates message assembly and model calls to dedicated modules
- `backend/services/agent/prompts.py`
  - central system prompt definition
  - organizes policy into sectioned rule groups (tool discipline, proposal workflows, execution, final response)
  - computes current-date context in user timezone (defaults to `America/Toronto`)
  - enforces entry-ingestion order: duplicate check first, then tag/entity reconciliation, then entry proposals
  - when a duplicate exists, prefers enriching the existing entry via `propose_update_entry` over creating a new duplicate entry
  - enforces canonical tag/entity normalization guidance (generalized merchant/location/entity names)
  - requires human-readable markdown note formatting for `markdown_notes` fields (preserve input detail; avoid headings for short notes; use line breaks/lists)
  - enforces tag-delete sequencing: update/retag affected entries before proposing `delete_tag`
  - requires `send_intermediate_update` as the first tool call when tools are needed, then sparse usage between meaningful tool-call batches
  - enforces name/selector-based proposals (no domain IDs in tool contracts)
  - includes a lightweight current-user context section (current user + owned accounts) at runtime
  - appends optional persistent `user_memory` from runtime settings to every system prompt
  - on tool errors/selector ambiguity, instructs the model to recover or ask for user clarification
- `backend/services/agent/message_history.py`
  - converts persisted thread history and attachments into model-ready messages
  - parses PDF attachments with PyMuPDF, normalizes text per line (trim + collapse internal whitespace), and appends extracted text into the user message content passed to the model
  - checks LiteLLM model vision capability and, when supported, renders uploaded PDF pages to PNG data URLs (one page per image part)
  - builds account summaries for current user and injects them into the system prompt context
  - includes account-level markdown notes in current-user context (`notes_markdown`) with truncation safeguards for large notes/data-url images
  - prepends reviewed proposal outcomes to the latest user message before user feedback text
  - for follow-up turns after interrupted runs, injects an interruption-context note so the model treats the prior request as unfinished context
- `backend/services/agent/model_client.py`
  - LiteLLM client adapter with normalized model error handling
  - normalizes usage metadata from model responses into the runtime contract (`input/output/cache_*` tokens), including provider-specific cache field variants (`cached_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`)
  - for prompt-caching-capable models, injects explicit LiteLLM `cache_control_injection_points` anchored to system context + latest user turn (negative message index) so tool-loop steps can reuse stable prompt prefixes
  - supports streamed model responses (`complete_stream`) that emit incremental text deltas and final assembled tool-call/message payload
  - applies configured retry policy to stream failures (including mid-stream transport failures)
  - performs a targeted one-shot retry for transient OpenRouter SSL `bad record mac` (`litellm.APIError`) failures in both streamed and non-streamed completions, including when `agent_retry_max_attempts=1`
  - suppresses duplicate streamed prefixes across retries so front-end token rendering remains incremental
  - forwards observability fields through LiteLLM `metadata` for Langfuse trace/session/user linking and through `extra_body` for providers that support it; supports `trace_id=thread_id` (one trace per thread), `is_first_run_in_thread`, `run_index`, and `step` for per-run/step generation names (`agent_turn_run_N_step_M`) and `existing_trace_id` for continuation steps or subsequent runs
  - enables LiteLLM `langfuse` success/failure callbacks when Langfuse credentials are configured
  - applies configurable tenacity retries for model completion calls
- `backend/services/agent/pricing.py`
  - LiteLLM-backed usage pricing helper (`cost_per_token`)
  - pricing lookup uses the configured model name directly
  - periodic model-cost map refresh from LiteLLM URL with fallback to bundled map when remote fetch fails
- `backend/services/agent/tools.py`
  - read tools: `list_entries`, `list_tags`, `list_entities`, `get_dashboard_summary`
  - progress tool: `send_intermediate_update` (brief user-visible intermediate reasoning/progress note; first tool call when tool work is needed)
  - entry proposal tools include explicit `markdown_notes` style guidance for human-readable, information-complete markdown
  - `list_entries` is the single entry query tool (date/name/from/to/tags/kind; exact-first then fuzzy ranking)
  - `list_tags` / `list_entities` support name+category query and include category in outputs
  - proposal tools cover CRUD:
    - entries: `propose_create_entry`, `propose_update_entry`, `propose_delete_entry`
    - tags: `propose_create_tag`, `propose_update_tag`, `propose_delete_tag`
    - entities: `propose_create_entity`, `propose_update_entity`, `propose_delete_entity`
  - proposal mutation tool:
    - `update_pending_proposal` (edit existing pending proposal payload by id + patch map)
    - `remove_pending_proposal` (remove existing pending proposal by id from current thread pending pool)
  - all model-facing tool interfaces avoid domain IDs (names/selectors only)
  - proposal tools now return proposal ids (`proposal_id`, `proposal_short_id`) in tool outputs
  - pending proposals from prior runs no longer block new `propose_*` tool calls in the same thread
  - `propose_delete_tag` returns `ERROR` when the tag is still referenced by non-deleted entries (with count + sample context)
  - proposal tools only create `agent_change_items` (`PENDING_REVIEW`)
- `backend/services/runtime_settings.py`
  - resolves effective runtime settings from `runtime_settings` overrides + env defaults where applicable
  - carries optional DB-backed `user_memory` text for agent prompt injection
  - exposes read-model payload for `/settings` API (`effective values + override metadata`)
  - used by agent runtime, dashboard currency selection, current-user attribution defaults, and entry-currency fallback
- `backend/services/agent/review.py`
  - per-item approve/reject workflow and state transitions
  - delegates concrete resource application to `backend/services/agent/change_apply.py`
- `backend/services/agent/change_apply.py`
  - change-type handler registry for full proposal CRUD across entries/tags/entities
  - entry update/delete resolve targets via selector (`date + amount_minor + from_entity + to_entity + name`)
  - tag delete is blocked when referenced by non-deleted entries (no automatic detach-on-delete)
  - entity delete applies null/detach semantics and preserves impacted entries/accounts
  - create-entry apply now writes directly without any entry status field
- `backend/services/agent/serializers.py`
  - timeline-ready nested serializer helpers

## Routers

Core routers:

- `accounts.py`
- `entries.py`
- `links.py`
- `groups.py`
  - `GET /api/v1/groups`: list derived linked-group summaries (`entry_count >= 2`, `edge_count`, date range, latest entry name)
  - `GET /api/v1/groups/{group_id}`: fetch one group graph (`nodes` + `edges`)
- `dashboard.py`
- `users.py`
- `entities.py`
- `entities.py` category responses now resolve through taxonomy assignments during updates, so renamed taxonomy terms are reflected immediately
- `tags.py`
- `taxonomies.py`
- `currencies.py`
- `settings.py`

Agent router:

- `backend/routers/agent.py`
- endpoints:
  - `GET /api/v1/agent/threads`
  - `POST /api/v1/agent/threads`
  - `DELETE /api/v1/agent/threads/{thread_id}`
  - `GET /api/v1/agent/threads/{thread_id}`
  - `POST /api/v1/agent/threads/{thread_id}/messages` (multipart text + image/PDF attachments)
  - `POST /api/v1/agent/threads/{thread_id}/messages/stream` (multipart text + image/PDF attachments, SSE response)
  - `GET /api/v1/agent/runs/{run_id}`
  - `POST /api/v1/agent/runs/{run_id}/interrupt`
  - `POST /api/v1/agent/change-items/{item_id}/approve`
  - `POST /api/v1/agent/change-items/{item_id}/reject`
  - `GET /api/v1/agent/attachments/{attachment_id}`

Settings router:

- `backend/routers/settings.py`
- endpoints:
  - `GET /api/v1/settings`
  - `PATCH /api/v1/settings`

## Migrations

- `0001_initial`
- `0002_entities_and_entry_entity_refs`
- `0003_entity_category`
- `0004_users_and_account_entity_links`
- `0005_remove_attachments`
- `0006_agent_append_only_core`
- `0007_taxonomy_core`
- `0008_agent_run_usage_metrics`
- `0009_remove_entry_status`
- `0010_runtime_settings_overrides`
- `0011_remove_openrouter_runtime_settings_fields`
- `0012_remove_related_link_type`
- `0013_add_account_markdown_body`
- `0014_remove_account_institution_type`
- `0015_add_agent_tool_call_output_text`
- `0016_add_user_memory_to_runtime_settings`

Commands:

- apply: `uv run alembic upgrade head`
- inspect state: `uv run alembic current`

## Testing

Test modules:

- `backend/tests/test_entries.py`
- `backend/tests/test_finance.py`
- `backend/tests/test_agent.py`
- `backend/tests/test_agent_model_client.py`
- `backend/tests/test_agent_pricing.py`
- `backend/tests/test_taxonomies.py`
- `backend/tests/test_settings.py`

`test_agent.py` covers:

- thread timeline persistence
- thread deletion (`DELETE /agent/threads/{thread_id}`), including running-run conflict checks and attachment-file cleanup
- final assistant message requirement
- tool call persistence
- unknown tool handling with persisted error status
- proposal generation for all change types
- approve/reject transitions
- approve conflict behavior
- apply failure transition to `APPLY_FAILED`
- entry apply creates persisted entries without an entry-level status property
- run usage token persistence (`input/output/cache read/cache write`) including multi-step aggregation and null-safe fallback
- run API cost fields (`input_cost_usd`, `output_cost_usd`, `total_cost_usd`)
- asynchronous run start behavior (`POST /agent/threads/{thread_id}/messages` returns `running` while execution continues)
- SSE agent message behavior (`POST /agent/threads/{thread_id}/messages/stream`) with incremental `text_delta` events, `reasoning_update` events, and terminal completion/failure events
- run interruption endpoint behavior (`POST /agent/runs/{run_id}/interrupt`) and no-op semantics for already-terminal runs
- interrupted-run context injection into the next user turn prompt input
- observability context propagation for stable per-thread session grouping
- LiteLLM routing behavior with provider env credential resolution
- prompt contract for entry ingestion ordering (duplicate check -> tag/entity reconciliation -> entry proposal)
- prompt contract for tag-deletion ordering (retag/update entries first -> then `propose_delete_tag`)
- prompt contract for parallelization: independent tools should be called in the same tool-call batch when possible
- prompt contract for sparse intermediate reasoning updates (`send_intermediate_update`) during multi-step tool loops

`test_agent_model_client.py` covers:

- completion retry behavior for transient pre-response failures
- stream retry behavior after partial output without duplicate text emission
- stream divergence guard across retries
- LiteLLM environment-validation behavior (including indeterminate-validation fallback)

Current baseline for `backend/tests/test_agent.py`: `52 passed`.

## Operational Impact

- agent image uploads are persisted under `.data/agent_uploads`
- deleting a thread removes its persisted attachment directories under `.data/agent_uploads/<message_id>/...`
- timeline rendering depends on attachment-serving endpoint
- non-stream sends execute in a background thread; `POST /agent/threads/{thread_id}/messages` returns immediately with `status=running`
- stream sends execute in-request and emit SSE events from `POST /agent/threads/{thread_id}/messages/stream`; disconnect fallback resumes the run in a background thread
- `DELETE /api/v1/agent/threads/{thread_id}` returns `409` while that thread has any running run
- streamed runs may emit `reasoning_update` events in addition to `tool_call` and `text_delta` events, enabling lightweight progress UI before final message persistence
- if a model emits assistant text in the same step as tool calls, runtime persists that text as a synthetic `send_intermediate_update` tool call (`output_json.message`, `output_json.source="assistant_content"`) so polling/history and SSE both render it as progress instead of a final assistant message
- interrupted runs are marked `failed` with user-facing interruption reason text
- the next user turn after an interruption carries an explicit interruption note in model input (while preserving normal conversation history)
- model requests include observability payload (`user`, `session_id=thread.id`, trace metadata) with LiteLLM metadata mapping for Langfuse grouping; one trace per thread (`trace_id=thread.id`), per-step generation names (`agent_turn_run_N_step_M`), and `existing_trace_id` for continuation steps or subsequent runs in the same thread so Langfuse displays one trace per conversation
- each run includes persisted tool traces and change-item audit data
- tool calls are committed incrementally per tool call to support near-real-time polling visibility
- persisted tool calls now store both structured payload (`output_json`) and exact model-visible text (`output_text`)
- each run now includes nullable aggregated usage counters (`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`)
- each run API payload now includes nullable derived USD cost fields from LiteLLM pricing (`input_cost_usd`, `output_cost_usd`, `total_cost_usd`)
- cache counters include parsed provider-specific aliases for better cross-provider accuracy (`cache_read_input_tokens`/`cached_tokens` -> `cache_read_tokens`; `cache_creation_input_tokens` -> `cache_write_tokens`)
- final assistant messages are sanitized to drop empty boilerplate footers (`Tools used ... Pending review item ids: []`) when no pending review items exist
- runtime settings can be updated through `/api/v1/settings`; changes apply to subsequent requests/runs without restarting the app
- dashboard currency and default entry currency are now runtime-configurable
- current user attribution defaults (`owner`/review actor) now resolve from runtime settings rather than env-only config
- account create/read/update schemas no longer expose `institution` and `account_type`
- entry-ingestion prompts now require duplicate detection before any entry proposal, reducing duplicate proposal risk
- duplicate-handling prompts now require checking for complementary new information and preferring `propose_update_entry` on the existing entry when appropriate
- prompt policy now requires canonical/generalized tag/entity naming
- tag guidance is explicit: use general descriptor tags (for example, `groceries`, `dining`, `online`), avoid entity-like or merchant-name tags (for example, `credit`, `loblaw`, `heytea`), and omit locations unless the user explicitly requests location-specific tagging
- entity normalization still maps abbreviations/store-branch variants to canonical names (for example, `SBUX` -> `Starbucks`)
- prompt policy now has a dedicated new-proposal specifications section for entries, tags, and entities
- new entry specs require grounding proposed fields in explicit source facts and avoiding invented missing details
- prompt policy now requires entry retag/update proposals before tag deletion proposals when references exist
- prompt policy now requires parallel tool-call batches whenever operations are independent instead of serial one-by-one calls
- prompt policy now requires `send_intermediate_update` as the first tool call when the run needs tools
- system prompt rules are grouped into explicit markdown sections for tool discipline, workflow sequencing, new proposal specifications, error handling, and final response behavior
- pending-proposal workflow now supports intra-thread proposal edits/removals via `update_pending_proposal` / `remove_pending_proposal` (id + patch map or id-only, pending-only)
- entry domain no longer includes `status`; API/model/migration are synchronized on statusless entries
- group read models now include:
  - `GET /api/v1/groups` derived summaries for frontend group discovery
  - `GET /api/v1/groups/{group_id}` graph detail
- `/api/v1/groups` omits single-entry components so the read model focuses on linked groups
- group topology mutations remain link-driven (`POST /entries/{entry_id}/links`, `DELETE /links/{link_id}`); no first-class group CRUD endpoints
- dashboard API serves runtime-configured currency analytics payloads; entries in other currencies are excluded from that dashboard response
- new agent module boundaries reduce coupling and make it safer to add new model providers/change types
- taxonomy defaults (`entity_category`, `tag_category`) are auto-provisioned by service logic when missing
- tags now support optional `category` assignment via taxonomy terms while keeping existing tag APIs intact
- entity categories are sourced from taxonomy assignments; `entities.category` column is still synchronized for compatibility
- `PATCH /entities/{entity_id}` now refreshes category from taxonomy assignments in the response path, improving UI consistency after term renames

## Constraints / Known Limitations

- no auth/permissions; actor is current configured user string
- runtime settings are global to the app instance (no per-authenticated-user isolation yet)
- model provider routing is LiteLLM-based using provider env credentials
- no websocket transport; streaming uses SSE only
- polling is still required for full run snapshots/tool payload details outside streamed deltas
- no autonomous/background agent runs
- update/delete proposal types are supported and require review approval before apply
- taxonomy assignment storage uses string `subject_id` and does not enforce cross-table FK integrity for subject rows
- Langfuse SDK is constrained to `<3` because LiteLLM's legacy `langfuse` callback passes `sdk_integration`, which Langfuse v3 removed

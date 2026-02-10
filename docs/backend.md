# Backend Documentation

## Stack

- FastAPI
- SQLAlchemy 2.x
- Pydantic v2
- Alembic
- SQLite (local file)
- OpenRouter Chat Completions integration via `openai` Python SDK

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

Agent settings:

- `OPENROUTER_API_KEY` (recommended)
- `BILL_HELPER_OPENROUTER_API_KEY` (also accepted)
- `OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`)
- `AGENT_MODEL` (default `google/gemini-3-flash-preview`)
- `AGENT_MAX_STEPS` (default `100`)
- `AGENT_MAX_IMAGE_SIZE_BYTES` (default `5MB`)
- `AGENT_MAX_IMAGES_PER_MESSAGE` (default `4`)
- runtime pricing uses LiteLLM model-cost mapping (`litellm`) and refreshes cost map from LiteLLM source with local fallback

Behavior notes:

- app starts even without `OPENROUTER_API_KEY`
- only agent message execution is blocked (`503`) when key is missing
- settings are cached by `get_settings()` (`lru_cache`)

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
    - CAD-scoped monthly KPIs
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
  - aggregates model usage metrics across all model calls in a run and persists totals on `agent_runs`
  - delegates message assembly and model calls to dedicated modules
- `backend/services/agent/prompts.py`
  - central system prompt definition
  - enforces entry-ingestion order: duplicate check first, then tag/entity reconciliation, then entry proposals
  - enforces name/selector-based proposals (no domain IDs in tool contracts)
  - includes a lightweight current-user context section (current user + owned accounts) at runtime
  - on tool errors/selector ambiguity, instructs the model to recover or ask for user clarification
- `backend/services/agent/message_history.py`
  - converts persisted thread history and attachments into model-ready messages
  - builds account summaries for current user and injects them into the system prompt context
  - prepends reviewed proposal outcomes to the latest user message before user feedback text
- `backend/services/agent/model_client.py`
  - OpenRouter client adapter with normalized model error handling
  - normalizes usage metadata from model responses into the runtime contract (`input/output/cache_*` tokens)
  - applies configurable tenacity retries for model completion calls
- `backend/services/agent/pricing.py`
  - LiteLLM-backed usage pricing helper (`cost_per_token`)
  - OpenRouter-prefixed model alias fallback for pricing lookup (`openrouter/<model>`, then raw model)
  - periodic model-cost map refresh from LiteLLM URL with fallback to bundled map when remote fetch fails
- `backend/services/agent/tools.py`
  - read tools: `list_entries`, `list_tags`, `list_entities`, `get_dashboard_summary`
  - `list_entries` is the single entry query tool (date/name/from/to/tags/kind; exact-first then fuzzy ranking)
  - `list_tags` / `list_entities` support name+category query and include category in outputs
  - proposal tools cover CRUD:
    - entries: `propose_create_entry`, `propose_update_entry`, `propose_delete_entry`
    - tags: `propose_create_tag`, `propose_update_tag`, `propose_delete_tag`
    - entities: `propose_create_entity`, `propose_update_entity`, `propose_delete_entity`
  - all model-facing tool interfaces avoid domain IDs (names/selectors only)
  - `propose_*` calls are blocked while prior thread proposals remain `PENDING_REVIEW`
  - proposal tools only create `agent_change_items` (`PENDING_REVIEW`)
- `backend/services/agent/review.py`
  - per-item approve/reject workflow and state transitions
  - delegates concrete resource application to `backend/services/agent/change_apply.py`
- `backend/services/agent/change_apply.py`
  - change-type handler registry for full proposal CRUD across entries/tags/entities
  - entry update/delete resolve targets via selector (`date + amount_minor + from_entity + to_entity + name`)
  - tag/entity delete applies detach/null semantics and preserves impacted entries/accounts
  - create-entry apply now writes directly without any entry status field
- `backend/services/agent/serializers.py`
  - timeline-ready nested serializer helpers

## Routers

Core routers:

- `accounts.py`
- `entries.py`
- `links.py`
- `groups.py`
- `dashboard.py`
- `users.py`
- `entities.py`
- `entities.py` category responses now resolve through taxonomy assignments during updates, so renamed taxonomy terms are reflected immediately
- `tags.py`
- `taxonomies.py`
- `currencies.py`

Agent router:

- `backend/routers/agent.py`
- endpoints:
  - `GET /api/v1/agent/threads`
  - `POST /api/v1/agent/threads`
  - `GET /api/v1/agent/threads/{thread_id}`
  - `POST /api/v1/agent/threads/{thread_id}/messages` (multipart text + images)
  - `GET /api/v1/agent/runs/{run_id}`
  - `POST /api/v1/agent/change-items/{item_id}/approve`
  - `POST /api/v1/agent/change-items/{item_id}/reject`
  - `GET /api/v1/agent/attachments/{attachment_id}`

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

Commands:

- apply: `uv run alembic upgrade head`
- inspect state: `uv run alembic current`

## Testing

Test modules:

- `backend/tests/test_entries.py`
- `backend/tests/test_finance.py`
- `backend/tests/test_agent.py`
- `backend/tests/test_agent_pricing.py`
- `backend/tests/test_taxonomies.py`

`test_agent.py` covers:

- thread timeline persistence
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
- prompt contract for entry ingestion ordering (duplicate check -> tag/entity reconciliation -> entry proposal)

Current baseline: `44 passed`.

## Operational Impact

- agent image uploads are persisted under `.data/agent_uploads`
- timeline rendering depends on attachment-serving endpoint
- agent runs execute in a background thread; message send returns immediately with `status=running`
- each run includes persisted tool traces and change-item audit data
- tool calls are committed incrementally per tool call to support near-real-time polling visibility
- each run now includes nullable aggregated usage counters (`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`)
- each run API payload now includes nullable derived USD cost fields from LiteLLM pricing (`input_cost_usd`, `output_cost_usd`, `total_cost_usd`)
- final assistant messages are sanitized to drop empty boilerplate footers (`Tools used ... Pending review item ids: []`) when no pending review items exist
- entry-ingestion prompts now require duplicate detection before any entry proposal, reducing duplicate proposal risk
- entry domain no longer includes `status`; API/model/migration are synchronized on statusless entries
- dashboard API now serves CAD-only analytics payloads with richer chart-ready sections; non-CAD entry rows are excluded from dashboard aggregations
- new agent module boundaries reduce coupling and make it safer to add new model providers/change types
- taxonomy defaults (`entity_category`, `tag_category`) are auto-provisioned by service logic when missing
- tags now support optional `category` assignment via taxonomy terms while keeping existing tag APIs intact
- entity categories are sourced from taxonomy assignments; `entities.category` column is still synchronized for compatibility
- `PATCH /entities/{entity_id}` now refreshes category from taxonomy assignments in the response path, improving UI consistency after term renames

## Constraints / Known Limitations

- no auth/permissions; actor is current configured user string
- model provider is OpenRouter-only in current implementation
- no streaming responses in V1
- near-real-time timeline updates remain polling-based (no websocket/SSE)
- no autonomous/background agent runs
- update/delete proposal types are supported and require review approval before apply
- taxonomy assignment storage uses string `subject_id` and does not enforce cross-table FK integrity for subject rows

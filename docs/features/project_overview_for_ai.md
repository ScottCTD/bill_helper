# Bill Helper – Project Overview for AI Context

## 1. Project Overview

**What it is:** Self-hosted personal finance ledger with an AI chat assistant. You run the backend (e.g., Docker); clients include a **web app** (React), an **iOS app** (SwiftUI), and **Telegram** (PTB bot for chat, commands, and review). The assistant reads and proposes changes to financial records via a **human-in-the-loop review workflow**. Data changes are never applied without explicit approval.

**Tech stack:**


| Layer        | Stack                                                      |
| ------------ | ---------------------------------------------------------- |
| Frontend     | React, TypeScript, Vite, Tailwind CSS, shadcn/ui           |
| Backend      | FastAPI, SQLAlchemy, Pydantic, LiteLLM                     |
| Database     | SQLite                                                     |
| Migrations   | Alembic                                                    |
| Package mgmt | uv (Python), npm (frontend)                                |


**Architecture principles:**

- **Routers:** HTTP translation only (parsing, response mapping, status codes).
- **Services:** Domain logic and orchestration.
- **Storage:** Dedicated service modules, not routers.
- **Data flow:** Client → router → service → models; agent proposals are created through the workspace terminal plus `bh`, applied only after human review.

---

## 2. Agents – AI Tools, Workflows, and Capabilities

### 2.1 Agent Overview

- Tool-calling LLM via LiteLLM (OpenAI, Anthropic, Google, OpenRouter, Bedrock, etc.).
- **Review-gated:** agent proposes changes only; humans approve/reject before domain mutations.
- No direct domain writes; all creates/updates/deletes go through proposal → review → apply.

### 2.2 Agent Tools

**Model-visible tools:**

- `terminal` – executes `bash -lc` inside the per-user workspace container with injected backend/auth/thread/run env.
- `send_intermediate_update` – short user-visible progress note.
- `rename_thread` – rename current thread.
- `add_user_memory` – append persistent memory items (add-only).

**Workspace app interface:**

- The workspace image includes the `bh` CLI.
- Bill Helper reads and proposal/review actions now go through `bh` instead of a large direct CRUD tool catalog.
- Current CLI coverage includes status, entries, accounts, snapshots, reconciliation, groups, entities, tags, and current-thread proposals.

### 2.3 Agent Run Lifecycle

1. User sends message (background or streaming).
2. Backend persists message and attachments.
3. Run starts; tool-call loop via LiteLLM.
4. Proposals stored for review.
5. Stream emits text and run events (reasoning, tool lifecycle).
6. Run completes or fails.
7. Untitled threads: only rename exposed until title set.

### 2.4 Agent Features

- **Attachments:** Image and PDF; uploads are parsed with Docling into inline `parsed.md` plus workspace image-path hints, and the agent can call `read_image` later when visual inspection is needed.
- **Surface context:** Telegram gets adapted prompts/replies.
- **Model selection:** Dropdown to pick from available models; can change mid-conversation.
- **Bulk mode:** One thread per attached file, concurrent limit configurable.
- **Run interrupt:** User can stop a running agent.
- **Review results:** Prepended to latest message for continuation; agent iteratively improves proposals after feedback and inspects prior proposal state through `bh proposals list|get`.
- **Tool lifecycle:** Queued → running → completed/cancelled; collapsible observability (arguments, output).
- **Usage tracking:** Context tokens, input/output/cache tokens, cost estimates; thread-level footnote.
- **Custom provider:** Configurable base URL and API key in settings.
- **Intermediate updates:** Agent tool `send_intermediate_update` emits progress notes between tool calls (e.g. "Let me search your entries…"); shown in timeline before final message.
- **Parallel threads:** Multiple threads can run concurrently; composer is thread-scoped (Send on idle thread even when another runs).
- **Running indicator:** Sidebar shows which threads have active runs.
- **Agent context:** Receives account markdown notes in system prompt for grounding.
- **Tool contract:** The model-facing tool surface stays small; domain operations are expressed as CLI calls inside the workspace terminal. Proposal history remains thread-scoped and review-gated.

### 2.5 Review Workflow

- **Edit-before-approve:** Entry proposals can be edited in the review modal before approving; structured forms mirror entry editor.
- **Batch actions:** Approve All and Reject All (with confirmation).
- **Diff display:** Human-friendly values (amounts in major units, no raw JSON quotes); field order stable and readable.
- **Pending across turns:** Unresolved proposals stay pending and editable when user sends follow-up; agent can continue proposing or update pending via proposal id.
- **Reopen:** Applied/rejected items can be reopened for audit.

---

## 3. Backend Features

### 3.1 Backend Scope

- **Core:** Accounts (CRUD, snapshots, reconciliation), entries (CRUD, filtering, group context), groups, filter groups, dashboard (KPIs, charts, timeline).
- **Catalogs:** Entities, tags, users, taxonomies, currencies.
- **Agent:** Threads, messages, runs, reviews, attachments, workspace terminal execution.
- **Settings:** Runtime settings.
- **Auth:** Password-backed bearer sessions for the app and API.

### 3.2 Data and Integration

- SQLite database; agent uploads stored on server.
- LLM providers via LiteLLM; no bank sync or CSV ingestion yet.

---

## 4. Frontend Features

### 4.1 Routes

- Home – agent workspace
- Dashboard – analytics and charts
- Filters – saved filter groups
- Entries – list, filter, create, edit; entry detail with group graph
- Entities – entity catalog
- Groups – groups workspace
- Accounts – accounts workspace
- Properties – users, entities, tags, taxonomy
- Settings – runtime settings

### 4.2 Capabilities

- Layout: sidebar, page headers, workspace sections.
- **Table pattern:** Rightmost compact add button; double-click row to edit; consistent filter row layout across Entries, Accounts, Properties.
- Shared editors for entries, tags, groups; group graph visualization; markdown notes.
- Agent: chat panel, thread list (running indicator per thread), timeline, composer, model dropdown, usage bar, attachments, review modal.
- **Agent UX:** Assistant messages rendered as markdown. Tool calls collapsible. Run/tool blocks in assistant column. Thread-scoped composer (parallel threads supported). Stop targets selected thread only.
- Principal session for auth; startup gate until principal selected.

---

## 5. Telegram Features

### 5.1 Commands

- `/start`, `/help` – intro and help.
- `/new`, `/reset` – new backend thread.
- `/threads` – list threads.
- `/use <number|uuid>` – switch active thread.
- `/model [provider/model]` – get/set shared agent model.
- `/stop` – interrupt active run.
- `/status` – model, thread, run state.
- `/dashboard [YYYY-MM]` – KPI and chart images.
- `/topics on|off` – forum-topic routing (one thread per topic).

### 5.2 Behavior

- Private chats only; user allow-list.
- Accepts text, photos, images, PDFs.
- **Streaming:** Progressive message edits as text arrives; agent progress notes from send_intermediate_update shown.
- **Forum topics:** `/topics on` maps one Telegram topic ↔ one backend thread; messages in topic go to that thread.
- Pending review items as inline keyboards (approve/reject).
- Dashboard charts rendered as images (matplotlib).

---

## 6. iOS Features

- Dashboard tab: month view, KPIs, charts, reconciliation.
- Entries tab: list, detail, pull-to-refresh.
- Agent tab: threads, messages, run state, streaming, review cards.
- Composer: text + invoice/receipt attachments.
- Backend base URL configurable (env or scheme).

---

## 7. Finance Domain Features

### 7.1 Entries

- Manual entry ledger with income/expense/transfer tracking.
- Counterparty entities, tags, entry groups.
- Entry kinds: EXPENSE, INCOME, TRANSFER.
- Money in minor units per currency.
- **Entry editor:** Modal-based create and edit (Notion-like); properties plus optional markdown body. Swap from/to control. Ranked fuzzy tag picker. Optional direct group assignment; SPLIT groups require member role.

### 7.2 Entities

**What they are:** Counterparties in transactions — people, merchants, payees, banks, etc. Every entry has a "from" and "to" entity describing where money came from and went to.

**Types:**
- **Account entities:** Each account is an entity root; the account id and entity id are the same. These represent your bank accounts, wallets, etc.
- **Generic entities:** Non-account counterparties — stores, friends, landlords, employers. These live in the entity catalog and can be assigned taxonomy categories.

**Behavior:**
- When an entity is deleted, entries keep the preserved name text for historical display, but the link is cleared; the UI shows a missing-entity marker.
- Entity deletion is blocked if the entity has an associated account (must delete the account first).
- Tags describe what was spent on; entities describe who the transaction was with.

### 7.3 Accounts

Accounts are entity-root records (each account is also an entity). They represent bank accounts, wallets, etc., with optional markdown notes.

**Snapshots:** User-recorded bank balance checkpoints. The user adds snapshots manually from their bank app — they are not derived. Each snapshot has date, balance, and optional note. Snapshots partition the account timeline. Deleting a snapshot removes that checkpoint; reconciliation rebuilds around the remaining snapshots. List order is newest first.

**Reconciliation (interval-based):** Snapshots divide the timeline into intervals. For each pair of consecutive snapshots:
- Bank change = end balance − start balance (what the bank says changed).
- Tracked change = sum of entry effects in the interval (what you recorded).
- Delta = tracked change − bank change (untracked difference — "you're missing $X of transactions").

The most recent snapshot produces one **open interval** from that snapshot to today: tracked change only, no bank change or delta (no closing checkpoint yet). Entries on a snapshot date belong to the interval ending at that snapshot. **Reconciled** intervals (delta = 0) can be collapsed; **mismatched** intervals (delta ≠ 0) are highlighted so the user can find missing or incorrect entries.

**Delete semantics:** Deleting an account removes the account and its snapshots. Entries keep denormalized from/to labels; the UI shows missing-entity markers where the link was cleared.

### 7.4 Groups

- First-class typed groups with direct membership (entries or child groups). Graph derived from type plus membership; no explicit edge storage.
- **BUNDLE:** Fully connected graph over direct members.
- **SPLIT:** At most one PARENT; parent descendants must be EXPENSE, children must be INCOME; requires member roles.
- **RECURRING:** All descendants same EntryKind; edges form chronological chain.
- Group nesting limited to one level; child groups cannot be shared across parents.
- Entry detail and groups workspace show graph visualization.

### 7.5 Taxonomy

- Taxonomies, taxonomy terms, taxonomy assignments. Entity Categories and Tag Categories are first-class manageable tables.
- Entities and tags can be assigned to taxonomy terms (categories).
- Default entity categories: merchant, account, financial_institution, government, utility_provider, employer, investment_entity, person, placeholder, organization.
- Default tags seeded: expense (housing, grocery, dining_out, etc.), income (salary_wages, bonus, etc.), internal (internal_transfer, e_transfer, cash_withdrawal, one_time, needs_review).

### 7.6 Filter Groups

**What they are:** Reusable saved filter definitions that classify entries for analytics. Most groups are user-editable; the built-in `untagged` group is a computed system bucket.

**Default groups:** Five built-in groups provisioned per user: day-to-day (routine spending — groceries, dining, transport, etc.), one-time (irregular purchases), fixed (recurring obligations — rent, insurance, utilities), transfers (external money movement), untagged (expense entries with no tags, or tagged expense entries that match no other saved group, needing review).

**Rule model:** Each editable filter group has include and exclude conditions. Rules support: entry kind, tag inclusion, tag exclusion, internal-transfer flag, nested AND/OR logic. Default groups other than `untagged` can be edited; custom groups can overlap with each other.

**Usage:** Filter groups power dashboard expense breakdowns, daily/monthly charts, projections, and largest-expense classification. Entries list can open filtered by a chosen group. Internal transfers (both from and to are accounts) are excluded from dashboard KPIs and charts.

### 7.7 Dashboard

**Data rules:** Uses a single configurable dashboard currency; entries in other currencies are excluded from all calculations. Internal account-to-account transfers are excluded from KPIs, charts, and projections.

**Tabs and behavior:**
- **Overview:** Month/year toggle; KPI cards (expense, income, net); income vs expense trend bar (stacked by filter group); builtin filter-group spend breakdown in trend-order with per-group tag facets and explicit sqrt-scale labeling on both ranked and facet bars; small-multiple expense-group trends; projection bars for current month with solid actual spend, translucent forecast extensions, and explicit sqrt-scale labeling.
- **Daily Expense:** Day-to-day daily bar chart with average/median spend metrics; yearly mode switches to monthly filter-group bars.
- **Breakdowns:** Monthly spend by filter group plus by-tag, by-source-entity, and by-destination-entity breakdowns.
- **Insights:** Largest expenses with filter group badges.

**Navigation:** Scrollable timeline of months with expense activity; no manual month picker. Yearly view assembled from repeated month-scoped reads.

### 7.8 Catalogs

- Entities, tags, users, filter groups.
- Currencies catalog (read-only).

---

## 8. Auth and Session

- Principal header for protected routes.
- Local principal session; startup gate until principal selected.
- Admin vs non-admin; admin required for agent routes.

---

## 9. Configuration and Data Paths

- **Config cascade:** Env vars → `.env` in CWD → `~/.config/bill-helper/.env` → defaults.
- **Data:** Default `~/.local/share/bill_helper/` for SQLite and agent uploads. Override via `BILL_HELPER_DATA_DIR` or `BILL_HELPER_DATABASE_URL`.
- Shared config and data support Git worktree workflows (secrets and DB shared across worktrees).

---

## 10. Dev Tooling

- **Config cascade:** Env vars → `.env` in CWD → `~/.config/bill-helper/.env` → defaults.
- **Data:** Default `~/.local/share/bill_helper/` for SQLite and agent uploads. Override via `BILL_HELPER_DATA_DIR` or `BILL_HELPER_DATABASE_URL`.
- Shared config and data support Git worktree workflows (secrets and DB shared across worktrees).

## 10. Dev Tooling

- Start backend, frontend, telegram (if configured).
- Seed defaults and demo data.
- Env setup, docs sync check.

---

## 11. Benchmark and Evaluation

- LLM evaluation for bank-statement parsing.
- Tags, entities, entries scoring.

---

## 12. Integration Points

- LiteLLM for model routing and credentials.
- SQLite for persistence.
- Telegram API for the bot.
- Not implemented: bank sync, CSV import, external financial APIs.

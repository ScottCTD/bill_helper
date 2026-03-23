# 💰 Bill Helper

> Your finances, all in one place — with an AI that handles the heavy lifting so you don't have to.

Bill Helper is a **personal finance ledger with a built-in AI assistant**. Track entries, categorize spending, reconcile accounts, and ask your agent anything — from a receipt scan to a month-end summary. Everything lives together, everything talks to each other, and you stay in control the whole time.

---

## ✨ What makes it special

### 🤖 AI that does the work, not just the talking
Chat with the agent like a colleague. Drop in a receipt photo, a PDF bank statement, or just describe what happened — the agent reads your ledger, thinks it through, and **proposes** changes. You see every diff. You approve or reject. Nothing ever lands without your say-so. No babysitting your data, no manual grunt work.

### 🗂️ Everything in one place
Entries, accounts, entities, tags, groups, spending analytics, reconciliation — it's all connected. The agent has the full picture and can act across any of it in a single conversation.

### 📊 Beautiful spending insights
The dashboard breaks your money into filter groups — day-to-day, one-time, fixed, transfers, income — and renders timelines, category breakdowns, and trends. Actually understand where your money goes, month by month.

### 📄 Drop in a document, get entries back
Upload a bank PDF or a receipt image. The agent parses it with Docling OCR, reasons about the contents, and returns structured entries ready for your review. Categorizing a month of transactions takes minutes, not hours.

### 🏦 Account reconciliation that makes sense
Attach balance snapshots to any account. Get an interval-by-interval view of what the bank says changed vs. what you tracked — with a clear delta you can act on.

### 🌐 Use it from anywhere
- **Web app** — full-featured React interface
- **Telegram** — quick entry capture and queries from your phone
- **iOS** — SwiftUI app for on-the-go access *(partial, actively expanding)*

### 🧠 Bring your own model
Plug in any LiteLLM-compatible provider: Anthropic, OpenAI, OpenRouter, AWS Bedrock, or anything behind a compatible API. You're not locked into one model or one vendor — but yes, the agent calls an external API. Fully local model support is on the roadmap.

---

## 🚀 Getting started

### Prerequisites

- Python 3.13+
- Node.js 18+
- [`uv`](https://docs.astral.sh/uv/)
- Docker *(for the AI workspace — skip with `BILL_HELPER_AGENT_WORKSPACE_ENABLED=0`)*

### Step 1 — Clone and install

```bash
git clone https://github.com/ScottCTD/bill_helper.git
cd bill_helper
uv sync
cd frontend && npm install && cd ..
```

### Step 2 — Configure your environment

```bash
./scripts/setup_shared_env.sh --clean
```

Open the generated `.env` and add your LLM provider key:

```env
AWS_BEARER_TOKEN_BEDROCK=...   # Bedrock
# or OPENROUTER_API_KEY=...    # OpenRouter
# or OPENAI_API_KEY=...        # OpenAI
# or ANTHROPIC_API_KEY=...     # Anthropic
```

Full reference: [`docs/development.md`](docs/development.md) · `.env.example`

### Step 3 — Initialize the database

```bash
uv run alembic upgrade head
```

### Step 4 — Build the agent workspace image

```bash
docker build -t bill-helper-agent-workspace:latest -f docker/agent-workspace.dockerfile .
```

This packages the `bh` CLI and a browser IDE into an isolated Docker container where the agent runs. Rebuild it whenever you change backend or `bh` CLI code.

### Step 5 — Create your admin account

```bash
uv run python scripts/bootstrap_admin.py --name admin --password admin
```

### Step 6 — Launch 🎉

```bash
./scripts/dev_up.sh
```

| Surface | URL |
|---------|-----|
| 🌐 Web app | `http://localhost:5173` |
| ⚡ API | `http://localhost:8000/api/v1` |
| 📖 API docs | `http://localhost:8000/docs` |

Sign in at `/login` and you're live.

---

## ⚙️ Configuration

All settings use the `BILL_HELPER_` prefix and can be set via `.env` or the in-app **Settings** page.

| Variable | Default | Description |
|----------|---------|-------------|
| `BILL_HELPER_AGENT_MODEL` | `bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0` | LiteLLM model string |
| `BILL_HELPER_AGENT_MAX_STEPS` | `100` | Max tool-call steps per run |
| `BILL_HELPER_AGENT_WORKSPACE_ENABLED` | `true` | Enable per-user Docker workspace |
| `BILL_HELPER_AGENT_WORKSPACE_IMAGE` | `bill-helper-agent-workspace:latest` | Workspace Docker image tag |
| `BILL_HELPER_AGENT_WORKSPACE_DOCKER_BINARY` | `docker` | Docker CLI binary path |
| `BILL_HELPER_WORKSPACE_BACKEND_BASE_URL` | `http://host.docker.internal:8000/api/v1` | API URL reachable from inside the workspace |
| `BILL_HELPER_DEFAULT_CURRENCY_CODE` | `CAD` | Default currency for new entries |
| `BILL_HELPER_DASHBOARD_CURRENCY_CODE` | `CAD` | Currency shown in the dashboard |
| `CURRENT_USER_TIMEZONE` | `America/Toronto` | Timezone for agent date context |

---

## 🗺️ Planned work

Bill Helper is a prototype with a clear vision. Here's what's actively being planned or thought about:

### 🧪 Comprehensive benchmarks
The agent needs to be tested against a diverse set of real-world scenarios — complex receipts, multi-currency statements, ambiguous descriptions, bulk imports, edge-case categorization. The goal is a reproducible benchmark suite that measures proposal quality, step count, and accuracy across the full feature surface. This is a high-priority next step before expanding the model catalog.

### 📧 Email ingestion
Connect Gmail and Outlook mailboxes to automatically surface transaction-related emails (bank alerts, receipts, invoices) as import candidates. The agent would parse each email, propose entries, and route them through the standard review workflow — no automated writes, same approval model as today.

### 🐳 Docker Compose packaging
A single `docker compose` setup that bundles the backend, pre-built frontend static files, optional Telegram bot, and the agent workspace image. Goal: one command to run a fully production-ready self-hosted instance on any machine with Docker.

### 📱 Full iOS feature parity
The iOS app currently covers roughly 15 of ~60 API endpoints — read-only views, basic navigation, no real auth flow. The plan is to close that gap: entry creation, full agent interaction, account management, and proper session handling.

### 🔌 OpenAI Responses API support
LiteLLM handles most of the model abstraction today, but the OpenAI Responses API (vs. the Completions API) unlocks streaming improvements and new capabilities. Adding first-class support is on the list.

### 🗃️ Agent workspace database
An optional lightweight SQLite inside the per-user sandbox — not a replica of the authoritative ledger, but a scratchpad the agent can use to cache context, run exploratory queries, and reason across multi-step tasks without hammering the API.

### 🏦 Bank sync / CSV import
Automated ingestion from bank exports and CSV files — every imported transaction still goes through the review pipeline before landing in the ledger.

### 💱 FX / exchange rate conversion
Multi-currency support with live or cached exchange rates so the dashboard can present a unified view across currencies.

### 🏠 Fully local model support
Right now the agent depends on an external LLM API. The goal is to support locally-hosted models (Ollama and similar) so the entire stack — app, agent, and model — can run completely offline on your own hardware.

---

## 🛠️ Development

```bash
# Backend only
uv run bill-helper-api

# Frontend only
cd frontend && npm run dev

# Backend tests (fast)
OPENROUTER_API_KEY=test uv run pytest backend/tests -q -m "not workspace_docker"

# Backend workspace tests (requires Docker)
OPENROUTER_API_KEY=test uv run pytest backend/tests/test_agent_workspace.py -q -m workspace_docker

# Frontend tests
cd frontend && npm run test

# Frontend e2e (Playwright)
cd frontend && npm run test:e2e

# Design and docs consistency checks
uv run python scripts/check_llm_design.py
uv run python scripts/check_docs_sync.py

# Rebuild workspace image after backend / bh changes
docker build -t bill-helper-agent-workspace:latest -f docker/agent-workspace.dockerfile .
```

---

## 🗂️ Project structure

```
backend/          FastAPI application — routers, services, models, agent runtime
frontend/         React + Vite web app
  src/features/   Feature modules (agent, dashboard, entries, accounts, …)
ios/              SwiftUI iOS app (partial coverage)
telegram/         Telegram bot transport
alembic/          Database migrations
docker/           Dockerfiles, including the agent workspace image
scripts/          Dev, seed, and maintenance scripts
docs/             Extended documentation
```

---

## 📚 Documentation

- [Docs index](docs/README.md)
- [Architecture](docs/architecture.md)
- [Backend](docs/backend_index.md) · [Frontend](docs/frontend_index.md)
- [API reference](docs/api.md)
- [Features](docs/features/README.md)
- [Data model](docs/data_model.md)
- [Development guide](docs/development.md)
- [Completed tasks archive](docs/completed_tasks/README.md)

---

## 📝 Notes

- All API routes are Bearer-token protected.
- Admins can manage users, sessions, and run impersonation from `/admin`.
- Agent uploads are stored per-user under `{data_dir}/user_files/{user_id}/uploads`.
- Playwright e2e tests spin up the backend against a disposable copy of the data dir — your primary database is never touched.
- Telegram supports both bearer token (`TELEGRAM_BACKEND_AUTH_TOKEN`) and custom proxy headers (`TELEGRAM_BACKEND_AUTH_HEADERS`).

---

## License

MIT

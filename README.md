# Bill Helper

A local-first personal finance ledger with an AI-powered chat assistant that can read, create, update, and delete your financial records through a human-in-the-loop review workflow.

## Motivation

The goal is an all-in-one place to view and analyze personal finances — a central tool to manage all bank accounts across currencies, with balances kept up-to-date with what your bank apps show. The MVP focuses on managing daily expenses and incomes; richer financial management features follow later.

## Features

**AI Chat Assistant**
- Natural language interface for managing entries, tags, and entities
- Review-gated proposals — the agent proposes changes, you approve or reject each one
- Real-time token streaming with persisted per-tool lifecycle events
- Live thread usage metrics, including current context-window size and cumulative token/cost totals
- Image and PDF attachment support (bank statements, receipts)
- Provider-agnostic model routing via LiteLLM (OpenAI, Anthropic, Google, OpenRouter, etc.)

**Finance Tracking**
- Manual entry ledger with income/expense tracking, counterparty entities, and tags
- Accounts workspace with entity-root account records, optional markdown notes, reconciliation snapshots, and destructive delete flow that preserves ledger history labels
- Dashboard analytics with interactive charts (daily spend, breakdowns, projections)
- Taxonomy system for categorizing entities and tags, including delete flows for non-account entities and tags
- Entry grouping with first-class typed groups and derived graph visualization (React Flow)

**Developer Experience**
- SQLite database with Alembic migrations — no external DB required
- Hot-reload dev server for both backend and frontend
- 100+ backend tests, plus frontend unit + integration tests
- Configurable via environment variables or runtime settings UI

## Tech Stack

| Layer | Stack |
|-------|-------|
| Frontend | React, TypeScript, Vite, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, SQLAlchemy, Pydantic, LiteLLM |
| Database | SQLite (local file) |
| Migrations | Alembic |
| Package Management | uv (Python), npm (frontend) |

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/)

### 1. Install dependencies

```bash
git clone https://github.com/ScottCTD/bill_helper.git
cd bill_helper
uv sync --extra dev
cd frontend && npm install && cd ..
```

### 2. Configure environment

Create a shared env file so secrets work across all checkouts and [Git worktrees](https://git-scm.com/docs/git-worktree):

```bash
# Interactive: creates ~/.config/bill-helper/.env from the template
./scripts/setup_shared_env.sh --clean
# Then edit ~/.config/bill-helper/.env and add your keys
```

At minimum, set the API key for your chosen model provider:

```env
# Pick one provider credential for the agent model:
AWS_BEARER_TOKEN_BEDROCK=ABSK...          # default model uses Bedrock bearer-token auth
# OPENROUTER_API_KEY=your-key-here        # if using openrouter/* models
# OPENAI_API_KEY=your-key-here            # if using openai/* models
# ANTHROPIC_API_KEY=your-key-here         # if using anthropic/* models

# Optional: change the model (default: bedrock/us.anthropic.claude-sonnet-4-6)
# BILL_HELPER_AGENT_MODEL=openai/gpt-4.1-mini
# BILL_HELPER_AGENT_API_KEY=provider-key   # explicit app-level override for a custom endpoint
# BILL_HELPER_AGENT_BASE_URL=https://api.example.com/v1
```

See `.env.example` for all available variables. Configuration cascades: real env vars → `.env` in CWD → `~/.config/bill-helper/.env` → defaults. See `docs/adr/0003-xdg-shared-config-and-data.md` for the full design.

The app boots fine without any credentials — the agent chat simply returns a configuration error until a valid provider key is set.

### 3. Initialize database

```bash
uv run alembic upgrade head
```

### 4. Run

```bash
./scripts/dev_up.sh
```

This starts both backend and frontend, applies pending migrations, and opens:

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api/v1
- **API docs**: http://localhost:8000/docs

Press `Ctrl+C` to stop both services.

## How the Agent Works

1. Open the **Agent** page — this is the AI chat workspace.
2. Create or select a conversation thread.
3. Send a message (text, images, or PDFs).
4. The agent reads your data, reasons about it, and proposes changes.
5. Review proposals in the diff modal — approve, reject, or edit each one.

The agent never mutates your data directly. Every create, update, or delete goes through a proposal → review → apply pipeline.

## Configuration

All settings use a `BILL_HELPER_` prefix and can be set via `.env` or the in-app **Settings** page (runtime overrides are persisted in the database).

| Variable | Default | Description |
|----------|---------|-------------|
| `BILL_HELPER_AGENT_MODEL` | `bedrock/us.anthropic.claude-sonnet-4-6` | LiteLLM model identifier |
| `BILL_HELPER_AGENT_MAX_STEPS` | `100` | Max tool-call steps per run |
| `BILL_HELPER_DEFAULT_CURRENCY_CODE` | `CAD` | Default currency for new entries |
| `BILL_HELPER_DASHBOARD_CURRENCY_CODE` | `CAD` | Currency used in dashboard analytics |
| `CURRENT_USER_TIMEZONE` | `America/Toronto` | Timezone for agent date context |

See [docs/development.md](docs/development.md) for the full variable reference.

## Project Structure

```
backend/                  # FastAPI application
  db_meta.py              # SQLAlchemy metadata root (no runtime side effects)
  database.py             # Engine/session factories and request DB dependency
  routers/                # API route handlers
  services/agent/         # Agent runtime, tools, prompts, model client
  models.py               # ORM compatibility facade
  models_finance.py       # Ledger/account/taxonomy ORM models
  models_agent.py         # Agent run/review ORM models
  schemas.py              # API schema compatibility facade
  schemas_finance.py      # Ledger/dashboard/settings request/response schemas
  schemas_agent.py        # Agent thread/run/review request/response schemas
frontend/                 # React + Vite application
  src/features/agent/     # Agent workspace, timeline, and review feature
  src/features/           # Feature modules (agent, accounts, properties)
  src/pages/              # Route pages
ios/                      # SwiftUI iOS MVP shell, shared mobile core, and API tests
alembic/                  # Database migrations
scripts/                  # Dev and seed scripts
docs/                     # Extended documentation
skills/                   # Project-local Codex skills and maintenance workflows
```

## Testing

```bash
# Backend
uv run pytest

# Frontend
cd frontend && npm run test

# Frontend build check
cd frontend && npm run build

# iOS shell + API tests
xcodebuild -project ios/BillHelperApp.xcodeproj -scheme BillHelperApp -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:BillHelperAPITests test
```

## Documentation

Extended docs live in [`docs/`](docs/):

- [Docs Index](docs/README.md)
- [Architecture](docs/architecture.md)
- [Repository Structure](docs/repository-structure.md)
- [Backend](docs/backend.md)
- [Frontend](docs/frontend.md)
- [API](docs/api.md)
- [Data Model](docs/data-model.md)
- [Development Guide](docs/development.md)
- [Documentation System](docs/documentation-system.md)
- [Execution Plans](docs/exec-plans/README.md)
- [Agent Billing Assistant](docs/agent-billing-assistant.md)

Package-local `backend/README.md` and `frontend/README.md` are intentionally thin navigation docs that point back to these canonical references.

## License

MIT

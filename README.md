# Bill Helper

A local-first personal finance ledger with an AI-powered chat assistant that can read, create, update, and delete your financial records through a human-in-the-loop review workflow.

## Features

**AI Chat Assistant**
- Natural language interface for managing entries, tags, and entities
- Review-gated proposals — the agent proposes changes, you approve or reject each one
- Real-time token streaming with tool-call observability
- Image and PDF attachment support (bank statements, receipts)
- Provider-agnostic model routing via LiteLLM (OpenAI, Anthropic, Google, OpenRouter, etc.)
- Optional Langfuse tracing for observability

**Finance Tracking**
- Manual entry ledger with income/expense tracking, counterparty entities, and tags
- Accounts workspace with optional markdown notes and reconciliation snapshots
- Dashboard analytics with interactive charts (daily spend, breakdowns, projections)
- Taxonomy system for categorizing entities and tags
- Entry grouping with link-driven graph visualization (React Flow)

**Developer Experience**
- SQLite database with Alembic migrations — no external DB required
- Hot-reload dev server for both backend and frontend
- 107 backend tests, frontend unit + integration tests
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

- Python 3.12+
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

Create a `.env` file in the project root. At minimum, set the API key for your chosen model provider:

```env
# Pick one provider credential for the agent model:
OPENROUTER_API_KEY=your-key-here          # default model uses OpenRouter
# OPENAI_API_KEY=your-key-here            # if using openai/* models
# ANTHROPIC_API_KEY=your-key-here         # if using anthropic/* models

# Optional: change the model (default: openrouter/moonshotai/kimi-k2.5)
# BILL_HELPER_AGENT_MODEL=openai/gpt-4.1-mini

# Optional: Langfuse observability
# LANGFUSE_PUBLIC_KEY=pk-lf-...
# LANGFUSE_SECRET_KEY=sk-lf-...
```

The app boots fine without any credentials — the agent chat simply returns a configuration error until a valid provider key is set.

### 3. Initialize database

```bash
uv run alembic upgrade head
```

Optionally seed demo data from a credit-card CSV export:

```bash
uv run python scripts/seed_demo.py /path/to/your/credit_card_export.csv
# or: BILL_HELPER_SEED_CREDIT_CSV=/path/to/csv ./scripts/dev_up.sh
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

1. Open the **Home** page — this is the AI chat workspace.
2. Create or select a conversation thread.
3. Send a message (text, images, or PDFs).
4. The agent reads your data, reasons about it, and proposes changes.
5. Review proposals in the diff modal — approve, reject, or edit each one.

The agent never mutates your data directly. Every create, update, or delete goes through a proposal → review → apply pipeline.

## Configuration

All settings use a `BILL_HELPER_` prefix and can be set via `.env` or the in-app **Settings** page (runtime overrides are persisted in the database).

| Variable | Default | Description |
|----------|---------|-------------|
| `BILL_HELPER_AGENT_MODEL` | `openrouter/moonshotai/kimi-k2.5` | LiteLLM model identifier |
| `BILL_HELPER_AGENT_MAX_STEPS` | `100` | Max tool-call steps per run |
| `BILL_HELPER_DEFAULT_CURRENCY_CODE` | `CAD` | Default currency for new entries |
| `BILL_HELPER_DASHBOARD_CURRENCY_CODE` | `CAD` | Currency used in dashboard analytics |
| `CURRENT_USER_TIMEZONE` | `America/Toronto` | Timezone for agent date context |

See [docs/development.md](docs/development.md) for the full variable reference.

## Project Structure

```
backend/                  # FastAPI application
  routers/                # API route handlers
  services/agent/         # Agent runtime, tools, prompts, model client
  models.py               # SQLAlchemy ORM models
  schemas.py              # Pydantic request/response schemas
frontend/                 # React + Vite application
  src/components/agent/   # Agent chat panel and review modal
  src/features/           # Feature modules (accounts, properties)
  src/pages/              # Route pages
alembic/                  # Database migrations
scripts/                  # Dev and seed scripts
docs/                     # Extended documentation
```

## Testing

```bash
# Backend
uv run pytest

# Frontend
cd frontend && npm run test

# Frontend build check
cd frontend && npm run build
```

## Documentation

Extended docs live in [`docs/`](docs/):

- [Architecture](docs/architecture.md)
- [Backend](docs/backend.md)
- [Frontend](docs/frontend.md)
- [API](docs/api.md)
- [Data Model](docs/data-model.md)
- [Development Guide](docs/development.md)
- [Agent Billing Assistant](docs/agent-billing-assistant.md)

## License

MIT

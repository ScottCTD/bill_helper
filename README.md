# Bill Helper

Bill Helper is a local-first personal finance ledger with a review-gated AI assistant. The current app supports multi-user password sessions, user-owned finance data, and owner-scoped agent threads.

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/)

### Install dependencies

```bash
git clone https://github.com/ScottCTD/bill_helper.git
cd bill_helper
uv sync
cd frontend && npm install && cd ..
```

### Configure environment

Create a shared env file so secrets work across worktrees:

```bash
./scripts/setup_shared_env.sh --clean
```

At minimum, add provider credentials for your chosen agent model. The default model uses Bedrock bearer-token auth:

```env
AWS_BEARER_TOKEN_BEDROCK=ABSK...
# or OPENROUTER_API_KEY=...
# or OPENAI_API_KEY=...
# or ANTHROPIC_API_KEY=...
```

See [`docs/development.md`](docs/development.md) and `.env.example` for the full variable set.

### Initialize the database

```bash
uv run alembic upgrade head
```

### Create or reset an admin login

```bash
uv run python scripts/bootstrap_admin.py --name admin --password admin
```

This is the supported bootstrap path for existing databases. On a brand-new demo database, `./scripts/dev_up.sh` may also seed demo data and create `admin` / `admin`.

### Run the app

```bash
./scripts/dev_up.sh
```

This starts:

- frontend: `http://localhost:5173`
- backend API: `http://localhost:8000/api/v1`
- API docs: `http://localhost:8000/docs`

Open the web app, sign in at `/login`, and use the password-backed session for all browser routes.

## Development Loop

- backend only: `uv run bill-helper-api`
- frontend only: `cd frontend && npm run dev`
- backend tests: `OPENROUTER_API_KEY=test uv run pytest backend/tests -q`
- frontend tests: `cd frontend && npm run test`
- browser e2e tests: `cd frontend && npm run test:e2e`
- docs sync: `uv run python scripts/check_docs_sync.py`

## Notes

- Protected API routes use `Authorization: Bearer <token>`.
- The web app supports password auth only.
- Admins can manage users and sessions from `/admin`, including impersonation sessions.
- Playwright e2e runs start the backend against a disposable copy of the shared data dir, so browser tests do not mutate the primary local database.
- Telegram transport can use `TELEGRAM_BACKEND_AUTH_TOKEN` for standard bearer auth or `TELEGRAM_BACKEND_AUTH_HEADERS` for custom proxy/header setups.

## How the Agent Works

1. Open the **Agent** page.
2. Create or select a conversation thread.
3. Send a message with text, images, or PDFs.
4. The agent reads your data, reasons about it, and proposes changes.
5. Review proposals in the diff modal and approve, reject, or edit them.

The agent never mutates your data directly. Every create, update, or delete goes through a proposal -> review -> apply pipeline.

## Configuration

All settings use a `BILL_HELPER_` prefix and can be set via `.env` or the in-app **Settings** page when they are runtime overrides.

| Variable | Default | Description |
|----------|---------|-------------|
| `BILL_HELPER_AGENT_MODEL` | `bedrock/us.anthropic.claude-sonnet-4-6` | LiteLLM model identifier |
| `BILL_HELPER_AGENT_MAX_STEPS` | `100` | Max tool-call steps per run |
| `BILL_HELPER_DEFAULT_CURRENCY_CODE` | `CAD` | Default currency for new entries |
| `BILL_HELPER_DASHBOARD_CURRENCY_CODE` | `CAD` | Currency used in dashboard analytics |
| `CURRENT_USER_TIMEZONE` | `America/Toronto` | Timezone for agent date context |

See [docs/development.md](docs/development.md) for the full variable reference.

## Project Structure

```text
backend/                  # FastAPI application
  db_meta.py              # SQLAlchemy metadata root (no runtime side effects)
  database.py             # Engine/session factories and request DB dependency
  routers/                # API route handlers
  services/agent/         # Agent runtime, tools, prompts, model client
  models_finance.py       # Ledger/account/taxonomy ORM models
  models_agent.py         # Agent run/review ORM models
  models_settings.py      # Runtime settings ORM model
frontend/                 # React + Vite application
  src/features/agent/     # Agent workspace, timeline, and review feature
  src/features/           # Feature modules
  src/pages/              # Route pages
ios/                      # SwiftUI iOS shell and tests
telegram/                 # Telegram transport, docs, entrypoints, and tests
alembic/                  # Database migrations
scripts/                  # Dev and seed scripts
docs/                     # Extended documentation
```

## Testing

```bash
# Backend
OPENROUTER_API_KEY=test uv run pytest backend/tests -q

# Frontend
cd frontend && npm run test

# Frontend build check
cd frontend && npm run build

# Frontend browser e2e
cd frontend && npm run test:e2e
```

## Documentation

Extended docs live in [`docs/`](docs/):

- [Docs Index](docs/README.md)
- [Architecture](docs/architecture.md)
- [Repository Structure](docs/repository_structure.md)
- [Backend](docs/backend_index.md)
- [Frontend](docs/frontend_index.md)
- [API](docs/api.md)
- [iOS](docs/ios_index.md)
- [Telegram](docs/telegram_index.md)
- [Features](docs/features/README.md)
- [Data Model](docs/data_model.md)
- [Development Guide](docs/development.md)
- [Documentation System](docs/documentation_system.md)
- [Completed Tasks Archive](docs/completed_tasks/README.md)
- [Agent Billing Assistant](docs/agent_billing_assistant.md)

Focused backend and frontend subsystem docs live in [`backend/docs/`](backend/docs/) and [`frontend/docs/`](frontend/docs/). Package-local navigation docs stay intentionally thin and point into those subsystem docs plus the top-level indexes.

## License

MIT

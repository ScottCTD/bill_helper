# Telegram Transport

This package contains the Bill Helper Telegram private-chat transport. It keeps Telegram-side update handling in `telegram/` and uses the existing backend thread/run/settings APIs instead of introducing a Telegram-specific backend stack.

## Current behavior

- uses `python-telegram-bot` (PTB) for commands, private-chat message intake, and polling/webhook execution
- enforces a Telegram user allow-list before processing any private-chat command or content message
- forwards text, photos, image documents, and PDFs into the existing Bill Helper agent thread/message flow
- stores the active backend thread and active run per Telegram chat in a local JSON state file
- renders replies as escaped Telegram HTML chunks instead of rich Markdown formatting

## Main entrypoints

- polling worker: `uv run python -m telegram.polling`
- webhook adapter: `uv run python -m telegram.webhook`
- package composition root: `telegram/commands.py`
- backend adapter: `telegram/bill_helper_api.py`
- per-chat state store: `telegram/state.py`

## Implemented features and endpoints

### User-facing Telegram features

- private-chat bot commands:
  - `/start`: intro and quick help
  - `/help`: command list plus supported upload types
  - `/new`: create and switch to a fresh backend thread
  - `/reset`: start a fresh thread without deleting older ones
  - `/threads`: list recent backend threads
  - `/use <number|thread-uuid>`: switch the active thread
  - `/model [provider/model]`: show or update the shared backend `agent_model`
  - `/stop`: interrupt the active run for the current chat
  - `/status`: show the current model, active thread, and run state
- non-command private-chat messages are forwarded into the active Bill Helper thread
- if a chat does not have an active thread yet, Telegram creates one automatically on the first message
- supported uploads: text, photos, image documents, and PDFs
- when a backend run stays in `running`, Telegram sends a temporary status reply and polls until a terminal result is available
- final replies are sent back as Telegram-safe HTML chunks

### Telegram transport HTTP endpoints

- `GET /healthz`: webhook-process health check
- `POST /telegram/webhook`: Telegram update receiver for webhook mode; requires `X-Telegram-Bot-Api-Secret-Token`

### Backend API endpoints used by the Telegram transport

- `GET /agent/threads`: list recent threads for `/threads` and `/use <number>`
- `POST /agent/threads`: create a new thread for `/new`, `/reset`, or first-message auto-creation
- `GET /agent/threads/{thread_id}`: validate or load the selected active thread
- `POST /agent/threads/{thread_id}/messages`: send Telegram text/files into an existing thread; includes `surface=telegram`
- `GET /agent/runs/{run_id}?surface=telegram`: poll active runs until completion
- `POST /agent/runs/{run_id}/interrupt`: implement `/stop`
- `GET /settings`: read runtime settings for `/status`, `/model`, and attachment limits
- `PATCH /settings`: update the shared backend `agent_model` for `/model <provider/model>`

## Local development

### Configure a bot and start polling

1. Create a bot with `@BotFather` in Telegram and copy the bot token.
2. Find your numeric Telegram user ID (for example via `@userinfobot`).
3. Add config in either repo-local `.env` or shared `~/.config/bill-helper/.env`:
   - `TELEGRAM_BOT_TOKEN=<bot-token-from-botfather>`
   - `TELEGRAM_ALLOWED_USER_IDS=<your-telegram-user-id>`
   - one model-provider credential for the backend agent, such as `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`
   - optional: `TELEGRAM_BACKEND_BASE_URL=http://localhost:8000/api/v1` when using a non-default backend URL
4. Start the backend API the bot should talk to:
   - `uv run alembic upgrade head`
   - `uv run bill-helper-api`
5. In a second terminal, start polling:
   - `uv run python -m telegram.polling`
6. Open a private chat with the bot and smoke-test with `/start`, `/help`, `/status`, or a normal text message.

Notes:

- `TELEGRAM_ALLOWED_USER_IDS` accepts either comma-separated integers or a JSON array.
- The bot is private-chat only and denies all users until the allow-list is configured.
- If the backend is running at the default local URL, `TELEGRAM_BACKEND_BASE_URL` can be omitted.

For webhook mode, also set `TELEGRAM_WEBHOOK_SECRET`, then run `uv run python -m telegram.webhook`.

The webhook module serves `GET /healthz` and accepts Telegram updates at `POST /telegram/webhook` on port `8081` when run via `python -m telegram.webhook`.

## Key configuration

- `TELEGRAM_BOT_TOKEN`: required in both polling and webhook modes
- `TELEGRAM_ALLOWED_USER_IDS`: required for real use; comma-separated integers or a JSON array of Telegram user IDs. The default is empty, which denies all private-chat commands and content messages.
- `TELEGRAM_WEBHOOK_SECRET`: required only for webhook mode
- `TELEGRAM_BACKEND_BASE_URL`: backend API base URL; defaults to `http://localhost:8000/api/v1`
- `TELEGRAM_API_BASE_URL`: optional Telegram API override; defaults to `https://api.telegram.org`
- `TELEGRAM_BACKEND_AUTH_TOKEN`: optional bearer token for backend requests
- `TELEGRAM_BACKEND_AUTH_HEADERS`: optional JSON object of backend headers; explicit `Authorization` here wins over `TELEGRAM_BACKEND_AUTH_TOKEN`
- `TELEGRAM_DATA_DIR`: optional transport data directory; defaults to `~/.local/share/bill-helper/telegram`
- `TELEGRAM_STATE_PATH`: optional override for the per-chat state JSON file; defaults to `<TELEGRAM_DATA_DIR>/chat_state.json`

`BILL_HELPER_TELEGRAM_*` aliases are accepted for the same settings.

## Current constraints

- private chats only; command and message handlers ignore non-private chats
- private-chat commands and content messages are default-deny until `TELEGRAM_ALLOWED_USER_IDS` is configured with authorized Telegram user IDs
- only PTB `message` updates are registered
- uploads are limited to photos, image documents, and PDFs; media-group coalescing is not implemented
- `/use` accepts only a positive list index or a backend thread UUID; invalid/path-like selectors are rejected before backend URL construction
- `/model` updates the shared backend runtime `agent_model` setting for the current environment

## Local docs

- `../docs/telegram_index.md`: cross-repo Telegram entry point
- `docs/README.md`: local Telegram docs index
- `docs/implementation-notes.md`: PTB wiring, backend adapter flow, state handling, and shim notes
- `../docs/development.md`: repo-wide Telegram run commands and verification commands
- `../backend/docs/runtime-and-config.md`: backend and Telegram env/config reference

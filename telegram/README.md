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

- `docs/README.md`: local Telegram docs index
- `docs/implementation-notes.md`: PTB wiring, backend adapter flow, state handling, and shim notes
- `../docs/development.md`: repo-wide Telegram run commands and verification commands
- `../docs/backend/runtime-and-config.md`: backend and Telegram env/config reference

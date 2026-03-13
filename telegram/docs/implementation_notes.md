# Telegram Implementation Notes

These notes describe the current Telegram transport implementation in this repository.

## Architecture summary

- `telegram/polling.py` loads settings, ensures the transport data directory exists, builds the PTB application, registers command metadata with Telegram, and runs polling with `allowed_updates=["message", "callback_query"]`.
- `telegram/webhook.py` wraps the same PTB application in a small FastAPI app, exposes `GET /healthz`, validates `X-Telegram-Bot-Api-Secret-Token`, and registers command metadata during startup before handing payloads to PTB.
- `telegram/commands.py` is the composition root for command routing, PTB handler registration, dashboard/topic commands, callback-query review handling, and application construction.
- `telegram/message_handler.py` owns Telegram message intake, attachment download, topic-aware thread routing, streamed run orchestration, fallback polling, topic rename sync, and final reply delivery.
- `telegram/stream_handler.py` owns progressive `edit_message_text` rendering plus periodic `typing` chat actions.
- `telegram/review_handler.py` renders pending review items and handles inline approve/reject callbacks.
- `telegram/charts.py` renders dashboard chart PNGs in-process for Telegram photo delivery.
- `telegram/bill_helper_api.py` stays thin: it uses `httpx` to call the existing backend `/agent/threads`, `/agent/runs/{id}`, `/agent/change-items/*`, `/dashboard`, and `/settings` routes and tags message/run reads with `surface=telegram` where needed.

## Important modules

- `config.py`: `TelegramSettings`, env parsing, Telegram user allow-list parsing, JSON header parsing, default data-dir/state-path derivation, and backend auth header synthesis.
- `state.py`: local JSON store keyed by Telegram `chat_id`, persisting `active_thread_id`, `active_run_id`, topic bindings, and rendered review-message IDs with atomic file replacement.
- `files.py`: downloads one Telegram photo or document attachment, enforces size limits, and accepts only image MIME types plus PDFs.
- `formatting.py`: escapes Telegram HTML, chunks replies to the Telegram 4096-character limit, formats dashboard KPI summaries and cost footers, and strips Markdown-heavy formatting for fallback replies.
- `__init__.py`: package convenience re-exports for the main Telegram transport types/functions.

## Request and reply flow

1. The polling or webhook entrypoint calls `build_application_from_settings()` from `telegram/commands.py`.
2. PTB command handlers register `/start`, `/help`, `/new`, `/reset`, `/threads`, `/use`, `/model`, `/stop`, `/status`, `/dashboard`, and `/topics`, plus one `CallbackQueryHandler` for review actions. Each path enforces the configured Telegram user allow-list before invoking transport logic.
3. The private-chat message handler accepts non-command text, photos, and documents only after the same allow-list check passes.
4. `TelegramContentHandler` resolves the target backend thread from either the active chat thread or a Telegram topic binding. When `/topics on` is enabled and content arrives from an unseen Telegram topic, the handler creates and binds a fresh backend thread before sending the message.
5. `BillHelperApiClient.stream_thread_message()` submits multipart content/files to the backend streaming route with `surface=telegram`.
6. `TelegramStreamConsumer` sends an initial placeholder, emits periodic `typing` chat actions, surfaces `reasoning_update` run events before text starts, and progressively edits Telegram messages as `text_delta` events arrive.
7. If SSE streaming drops or ends before a terminal run snapshot is available, the handler falls back to the existing background-run plus `GET /agent/runs/{run_id}?surface=telegram` polling path.
8. Completed replies are sent back as escaped HTML chunks with a small cost/model footer when usage data exists; if `terminal_assistant_reply` is absent, the handler falls back to the assistant message content from the thread detail response.
9. After completion, the handler optionally renames the bound Telegram topic for that backend thread to match the backend thread title and renders pending review items as inline-keyboard messages.

## PTB import-collision shim (`telegram/ptb.py`)

This repository has its own top-level `telegram/` package, which would normally shadow the upstream `telegram` package provided by `python-telegram-bot`.

Current workaround:

- `telegram/ptb.py` locates the installed `python-telegram-bot` distribution
- extends the local package `__path__` to include the upstream PTB package directory
- executes the upstream `telegram/__init__.py` into the current package namespace
- re-exports the PTB types used by this codebase (`Application`, `ApplicationBuilder`, `CommandHandler`, `MessageHandler`, `Update`, `filters`, and related types)

When editing this package, import PTB symbols from `telegram.ptb`, not directly from upstream `telegram`, so the local package and PTB stay interoperable.

## Current constraints and behavior

- private chats only; non-private chats are ignored by command and message handlers
- private-chat commands and content messages are default-deny until `TELEGRAM_ALLOWED_USER_IDS` (or `BILL_HELPER_TELEGRAM_ALLOWED_USER_IDS`) is configured with authorized Telegram user IDs
- only `message` and `callback_query` updates are registered with PTB
- one chat-state record is stored per Telegram chat, so thread/run selection is local to that chat ID
- `/reset` and `/new` create a fresh backend thread; `/reset` keeps older threads discoverable via `/threads`
- `/use` accepts a positive list index or backend thread UUID only; path-like selectors are rejected in the Telegram layer before backend URLs are built
- `/model` patches the shared backend runtime settings record rather than a Telegram-only model setting; it accepts either a full model identifier or a unique case-insensitive substring from `available_agent_models`
- `/dashboard` renders charts in the Telegram transport process with matplotlib instead of calling a backend image endpoint
- `/topics on` does not create Telegram topics; it only changes routing when Telegram supplies `message_thread_id`, and the first content message in an unseen Telegram topic creates and binds a fresh backend thread
- review actions support approve/reject and approve-all/reject-all only; reopen and reviewer payload overrides remain web-only
- attachment support is limited to a single photo or document per message; media-group/album coalescing is not implemented
- supported documents are image files and PDFs only
- webhook mode requires `TELEGRAM_WEBHOOK_SECRET`; `python -m telegram.webhook` binds uvicorn to `0.0.0.0:8081`
- backends should be configured with `TELEGRAM_BACKEND_AUTH_TOKEN`; `TELEGRAM_BACKEND_AUTH_HEADERS` remains available for proxy or custom header injection

## Developer checklist

- use `uv run python -m telegram.polling` or `uv run python -m telegram.webhook` for local execution
- keep transport-specific docs in this package and repo-wide behavior/docs in `../docs/`
- when changing config or behavior, update both `telegram/README.md` and the relevant stable docs in `docs/`

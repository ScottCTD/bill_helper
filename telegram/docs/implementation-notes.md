# Telegram Implementation Notes

These notes describe the current Telegram transport implementation in this repository.

## Architecture summary

- `telegram/polling.py` loads settings, ensures the transport data directory exists, builds the PTB application, and runs polling with `allowed_updates=["message"]`.
- `telegram/webhook.py` wraps the same PTB application in a small FastAPI app, exposes `GET /healthz`, and validates `X-Telegram-Bot-Api-Secret-Token` before handing the payload to PTB.
- `telegram/commands.py` is the composition root for command routing, PTB handler registration, and application construction.
- `telegram/message_handler.py` owns Telegram message intake, attachment download, backend run polling, and final reply delivery.
- `telegram/bill_helper_api.py` stays thin: it calls the existing backend `/agent/threads`, `/agent/runs/{id}`, and `/settings` routes and tags message/run reads with `surface=telegram` where needed.

## Important modules

- `config.py`: `TelegramSettings`, env parsing, JSON header parsing, default data-dir/state-path derivation, and backend auth header synthesis.
- `state.py`: local JSON store keyed by Telegram `chat_id`, persisting `active_thread_id` and `active_run_id` with atomic file replacement.
- `files.py`: downloads one Telegram photo or document attachment, enforces size limits, and accepts only image MIME types plus PDFs.
- `formatting.py`: escapes Telegram HTML, chunks replies to the Telegram 4096-character limit, and strips Markdown-heavy formatting for fallback replies.
- `__init__.py`: package convenience re-exports for the main Telegram transport types/functions.

## Request and reply flow

1. The polling or webhook entrypoint calls `build_application_from_settings()` from `telegram/commands.py`.
2. PTB command handlers register `/start`, `/help`, `/new`, `/reset`, `/threads`, `/use`, `/model`, `/stop`, and `/status`.
3. The private-chat message handler accepts non-command text, photos, and documents.
4. `TelegramContentHandler` ensures the chat has an active backend thread, fetches backend runtime settings, and downloads supported attachments.
5. `BillHelperApiClient.send_thread_message()` submits multipart content/files to the existing backend thread message route with `surface=telegram`.
6. If the returned run is still running, the handler polls `GET /agent/runs/{run_id}?surface=telegram` until a terminal state or timeout.
7. Completed replies are sent back as escaped HTML chunks; if `terminal_assistant_reply` is absent, the handler falls back to the assistant message content from the thread detail response.

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
- only message updates are registered with PTB
- one chat-state record is stored per Telegram chat, so thread/run selection is local to that chat ID
- `/reset` and `/new` create a fresh backend thread; `/reset` keeps older threads discoverable via `/threads`
- `/model` patches the shared backend runtime settings record rather than a Telegram-only model setting
- attachment support is limited to a single photo or document per message; media-group/album coalescing is not implemented
- supported documents are image files and PDFs only
- webhook mode requires `TELEGRAM_WEBHOOK_SECRET`; `python -m telegram.webhook` binds uvicorn to `0.0.0.0:8081`

## Developer checklist

- use `uv run python -m telegram.polling` or `uv run python -m telegram.webhook` for local execution
- keep transport-specific docs in this package and repo-wide behavior/docs in `../docs/`
- when changing config or behavior, update both `telegram/README.md` and the relevant stable docs in `docs/`
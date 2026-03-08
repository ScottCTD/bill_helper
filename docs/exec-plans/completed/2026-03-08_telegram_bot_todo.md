# Telegram Bot TODO

## Goal

Add a monorepo-native Telegram bot that lets a user talk to the existing Bill Helper agent from Telegram without creating a separate product stack.

The bot should stay thin: Telegram owns chat delivery, while Bill Helper keeps agent threads, attachments, model execution, review flows, and runtime settings as the source of truth.

## Product Decisions

- Add the bot in a new top-level `telegram/` directory inside the project root.
- Keep the repository monorepo shape: `backend/`, `frontend/`, `ios/`, `telegram/`, `docs/`.
- Treat the Telegram bot as a transport adapter over the existing agent APIs, not as a second agent implementation.
- Target Telegram private chats first.
- Support text chat plus image/PDF upload in MVP.
- Support thread-management commands in Telegram rather than inventing a custom bot-only workflow.
- Use Telegram HTML formatting for outbound bot messages; do not send Markdown-formatted agent replies to Telegram users.
- Preserve existing Bill Helper agent threads and reviews instead of creating Telegram-only persistence for agent state.

## Why This Fits The Current System

The existing backend already has the main surfaces the bot needs:

- agent thread list/create/read/update/delete endpoints
- agent message send endpoints with multipart file upload
- image/PDF attachment handling
- run interrupt support
- runtime setting support for `agent_model`

That means the Telegram layer can focus on:

- Telegram update intake
- chat-to-thread mapping
- file download from Telegram and re-upload to the backend
- Telegram-specific response formatting and command UX

## Monorepo Placement

Create a new top-level `telegram/` package in the project root.

Proposed shape:

```text
/telegram
  /README.md
  /docs
  /bot
    __init__.py
    main.py
    config.py
    webhook.py
    polling.py
    telegram_api.py
    bill_helper_api.py
    commands.py
    formatting.py
    state.py
    files.py
  /tests
```

Responsibilities:

- `telegram_api.py`: raw Telegram Bot API calls (`sendMessage`, `editMessageText`, `getFile`, etc.)
- `bill_helper_api.py`: calls into existing Bill Helper agent/settings endpoints
- `webhook.py`: FastAPI or equivalent webhook adapter for production
- `polling.py`: local-dev update loop
- `commands.py`: `/start`, `/help`, `/new`, `/reset`, `/threads`, `/use`, `/model`, `/stop`
- `formatting.py`: Telegram-safe HTML/plain-text rendering and chunking
- `state.py`: chat-to-active-thread mapping plus lightweight per-chat bot state
- `files.py`: Telegram file download, MIME validation, temp-file lifecycle, backend multipart upload bridge

`/docs/` stores all the implementation note for the telegram integration only. Keep things documented.

## MVP Scope

### Included

- send a text message from Telegram to the existing agent
- receive the agent reply in Telegram
- upload receipt/invoice images to the agent
- upload PDF statements/receipts to the agent
- manage the active conversation thread from Telegram commands
- change the active agent model from Telegram
- interrupt an in-flight run from Telegram
- apply a Telegram-specific agent response policy that avoids Markdown and uses Telegram-friendly formatting

### Explicitly Out Of Scope For MVP

- Telegram group chats and channel workflows
- Telegram inline mode
- Telegram Mini Apps
- payments
- full review/action UI inside Telegram beyond basic status links or summary text
- album/media-group coalescing across multiple Telegram messages
- separate Telegram-only memory, search, or data storage layer for agent content

## Thread And Session Model

Each Telegram private chat maps to one active Bill Helper agent thread at a time.

Rules:

- if a Telegram chat has no active thread yet, create one on first message or `/new`
- normal text and file messages are appended to the active thread
- old Bill Helper threads remain persisted; Telegram does not delete history when the user resets context
- `/reset` starts a fresh Bill Helper thread and makes it active for that Telegram chat
- `/new` also starts a fresh thread and makes it active immediately
- `/threads` lists recent Bill Helper threads relevant to the Telegram chat owner
- `/use <index-or-thread-id>` switches the active Bill Helper thread for that chat
- thread titles continue to come from the existing agent rename behavior unless the bot later adds an explicit rename command

For MVP, `/reset` is a safe reset of active context, not a destructive delete.

## Telegram Command Set

Use commands as the primary Telegram-native control surface:

- `/start`: explain what the bot can do and how uploads work
- `/help`: show commands and supported file types
- `/new`: create a fresh agent thread and switch the chat to it
- `/reset`: clear active context by creating a new blank thread and switching to it
- `/threads`: show recent threads with the active one marked
- `/use <index-or-thread-id>`: switch to an existing thread
- `/model <provider/model>`: update the configured model used for future runs
- `/stop`: interrupt the currently running agent run for the active thread if one exists
- `/status`: show active thread title/id, configured model, and whether a run is active

## Model Selection Policy

For MVP, `/model` should update the existing Bill Helper runtime setting `agent_model` through the current settings API.

That keeps the first implementation simple and aligned with the current system, where model selection already exists as a runtime setting rather than a Telegram-specific per-message override.

## File Intake Flow

Supported Telegram inputs for MVP:

- text-only messages
- photo uploads
- image documents
- PDF documents

Flow:

1. Telegram sends an update to the bot.
2. The bot resolves the active Bill Helper thread for that chat.
3. For file messages, the bot calls Telegram `getFile`, downloads the file bytes, validates type/size, and stores them in a temp location.
4. The bot forwards the message to Bill Helper using the existing multipart agent message endpoint.
5. The backend persists the message, attachments, and run as usual.
6. The bot sends a concise Telegram acknowledgement and later the final agent reply.

Implementation rule: the Telegram adapter should re-upload file bytes to Bill Helper, not pass Telegram-hosted file URLs into the core agent pipeline.

## Telegram Response Formatting Policy

Telegram replies should be optimized for chat readability, not web Markdown rendering.

Required behavior:

- introduce a Telegram-specific response mode in the agent prompt path
- instruct the agent to avoid Markdown headings, tables, fenced code blocks, and long markdown-heavy formatting
- prefer short paragraphs, simple bullets, compact numbered steps, and plain-language summaries
- render outbound Telegram messages with `parse_mode=HTML` only when needed for light emphasis
- escape all Telegram HTML-sensitive content before sending
- split long replies into safe Telegram-sized chunks
- keep attachment/result acknowledgements concise and conversational

Prompt requirement for Telegram runs:

- the agent must know the current surface is Telegram
- the final response style for Telegram must be plain, readable, and non-Markdown
- if structured output is needed, use plain bullets or Telegram-safe HTML emphasis only

## Backend Integration Direction

The Telegram bot should reuse these existing backend capabilities:

- `POST /api/v1/agent/threads`
- `GET /api/v1/agent/threads`
- `GET /api/v1/agent/threads/{thread_id}`
- `POST /api/v1/agent/threads/{thread_id}/messages`
- `POST /api/v1/agent/runs/{run_id}/interrupt`
- `PATCH /api/v1/settings` for `agent_model`

Needed backend-facing additions for clean Telegram support:

- a small prompt-context extension so agent execution can declare `surface=telegram`
- response-formatting support that is channel-aware without forking the full agent runtime
- an easy way for the Telegram adapter to read the latest terminal assistant reply for a submitted run

The Telegram work should not duplicate agent business logic in the bot layer.

## Delivery Strategy

Use long polling for local development and a webhook endpoint for production.

Production requirements:

- Telegram webhook endpoint with secret-token verification
- bot token stored in environment/shared config, never committed
- structured logging for Telegram update id, chat id, command, thread id, and run id

## TODO Checklist

- create `telegram/` top-level package in the monorepo
- add bot config for Telegram token, webhook secret, backend base URL, and auth headers
- implement Telegram Bot API client wrapper
- implement Bill Helper API client wrapper for threads, messages, interrupt, and settings
- add chat-to-active-thread state storage keyed by Telegram `chat_id`
- create local-dev polling entrypoint
- create production webhook entrypoint with secret validation
- implement `/start`, `/help`, `/new`, `/reset`, `/threads`, `/use`, `/model`, `/stop`, and `/status`
- implement text-message forwarding to the active Bill Helper thread
- implement Telegram photo/image/PDF download and multipart re-upload to the backend agent endpoint
- validate file type and size before forwarding uploads
- add progress acknowledgements for long-running agent work
- add interrupt wiring so `/stop` cancels the active run when possible
- add Telegram-specific prompt context to the agent prompt builder
- add Telegram-safe final-response rendering with no Markdown output
- add message chunking and HTML escaping for outbound Telegram replies
- document local Telegram bot dev flow in `README.md` and `docs/development.md` once implementation starts
- update stable backend/API docs when the Telegram integration endpoints or prompt contracts land

## Recommendation To Follow

Build the Telegram bot as a thin top-level monorepo service in `telegram/` that reuses the existing Bill Helper thread/message/runtime APIs, supports text plus image/PDF intake, exposes Telegram commands for thread and model control, and adds a Telegram-specific non-Markdown response mode so agent replies read cleanly inside Telegram.
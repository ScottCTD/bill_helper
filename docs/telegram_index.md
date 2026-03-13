# Telegram Documentation

This file is the Telegram index. Use it to find the transport docs under `../telegram/docs/`.

## Telegram Doc Map

- `../telegram/README.md`: local package overview, run commands, and config summary.
- `../telegram/docs/README.md`: topic map for Telegram-specific behavior docs.
- `../telegram/docs/implementation_notes.md`: PTB wiring, backend adapter flow, state persistence, and shim notes.

## Stable Boundaries

- Telegram update handling, formatting, and state persistence live under `telegram/`.
- The transport reuses existing backend thread, run, and settings APIs instead of adding a Telegram-specific backend stack.
- The transport now also owns Telegram-native streaming, inline review actions, dashboard chart rendering, and optional forum-topic thread mapping.
- Telegram-specific transport behavior belongs in `telegram/docs/*.md`, while cross-repo workflow and backend/API references stay under `docs/`.

## Related Docs

- `docs/development.md`
- `docs/api.md`
- `docs/backend_index.md`

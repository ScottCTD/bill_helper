# Telegram Docs

This directory holds Telegram-transport-specific documentation that should stay close to the code under `telegram/`.

Start with `../README.md` for the package overview, run commands, and config summary, then use the files here for implementation detail.

## Files

- `implementation_notes.md`: PTB application flow, key modules, backend adapter boundaries, state persistence, and the `telegram/ptb.py` shim.

## Scope

- Telegram transport behavior that is specific to this package
- implementation details that do not belong in the repo-wide docs tree
- current module responsibilities and developer notes for working inside `telegram/`
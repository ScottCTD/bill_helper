# Markdown Editor Vite Fix Log

Date: 2026-03-10

## Summary

This fix log records the debugging path and durable fixes for the entries/groups/accounts white-page regression and the follow-on markdown editor fallback failures in local development.

Visible symptoms:

- clicking `Entries`, `Groups`, or `Accounts` could blank the page when the route transitively loaded the markdown editor stack
- after route isolation, editor dialogs could still fall back to a plain textarea because Vite dev mode was serving stale optimized dependency chunks or breaking CommonJS/ESM interop inside the BlockNote dependency tree

## Findings and durable fixes

| Finding | What looked wrong | Durable fix |
|---|---|---|
| Route navigation was coupled to the BlockNote bundle | Listing pages for entries, groups, and accounts could fail before any editor UI opened | Split the exported markdown editor into a thin wrapper plus `MarkdownBlockEditorImpl`, so the heavy BlockNote bundle loads only when an editor dialog mounts |
| The first textarea fallback was too quiet for development | The app remained usable, but the runtime failure was easy to miss | Kept the textarea fallback but changed dev builds to render an explicit alert with the captured runtime error above the textarea |
| Excluding BlockNote from `optimizeDeps` fixed stale chunks but broke the editor stack | Raw CommonJS dependencies such as `extend` and `fast-deep-equal` then failed with browser module-loader `SyntaxError`s | Reverted the exclusion approach and set `optimizeDeps.force = true` in `frontend/vite.config.ts` so each dev-server start rebuilds optimized dependencies with the normal interop pipeline intact |
| `dev_up.sh` still reused stale optimized frontend cache output across restart loops | Local runs could carry forward broken `.vite` output even after code fixes landed | `scripts/dev_up.sh` now removes `frontend/node_modules/.vite` before launching the frontend dev server |

## Regression coverage

- Added `frontend/src/components/MarkdownBlockEditor.test.tsx` coverage for:
  - the loading-state textarea fallback before the rich editor chunk resolves
  - the dev-only alert path when the lazy editor import throws

## Prevention notes

- Keep the markdown editor wrapper thin so route pages do not hard-depend on BlockNote.
- For developer clarity, prefer loud dev-only diagnostics over silent fallback behavior.
- When a Vite restart bug involves `.vite/deps`, prefer rebuilding the optimizer cache on startup over selectively excluding a complex dependency tree unless the interop story is proven end-to-end.

# Agent Thread Rename UI Fix Log

Date: 2026-03-07

## Summary

This fix log records the debugging path and durable frontend fixes for the agent thread inline-rename UI. The visible symptoms were:

- an inner partial border appearing during rename
- text size looking slightly larger while editing
- the title jumping vertically when switching between read and edit states

## Findings and durable fixes

| Finding | What looked wrong | Attempt(s) ruled out | Durable fix |
|---|---|---|---|
| Global input chrome leaked into inline rename | Rename mode showed a nested left/right border inside the thread pill | Local `agent-thread-input` border/ring resets alone did not win | Excluded `.agent-thread-input` from the app-wide base selector `input:not([type="checkbox"]):not([type="file"])` so the inline rename field no longer inherits standard form-control border/shadow/ring styling |
| Shared UI input styling was too heavyweight for inline editing | Even after local CSS tweaks, the rename surface still behaved like a full form field | Re-tuning the shared `Input` component styles was not appropriate because the problem was specific to this inline editor | Replaced the shared `Input` usage in `frontend/src/features/agent/panel/AgentThreadList.tsx` with a dedicated inline editor surface |
| Native input text rendering still differed from the display label | Edit-mode text could appear slightly larger or rasterized differently | Font inheritance and appearance resets reduced noise but did not fully remove the mismatch | Replaced the native text input with a small `contentEditable` textbox so edit mode uses the same text rendering path as normal inline text |
| Shared button component changed read-state text positioning | The non-editing label sat slightly lower than the editing label, causing a visible vertical jump | Label and input line-height/padding tweaks helped but did not fully remove the mismatch | Replaced the shared `Button` wrapper for the display title with a plain styled `button`, so read and edit states share much closer layout and typography behavior |
| Read/edit layouts reserved different right-side space | Text shifted horizontally when switching modes | Minor padding tweaks alone were insufficient while the wrappers still differed | Matched the thread-title display/edit geometry by aligning right padding reservation and text-height handling in `frontend/src/styles.css` |

## Final state

The thread rename UI now uses lightweight dedicated primitives instead of shared form/button components:

- read state: plain styled `button`
- edit state: plain `contentEditable` textbox

That keeps the thread row visually stable and avoids nested control chrome inside the rounded thread shell.

## Prevention notes

- Do not use the app-wide shared `Input` component for inline editors that must visually disappear into an existing shell.
- Be careful with global base selectors for `input`; inline-edit affordances may need an explicit opt-out.
- For pixel-sensitive inline rename UIs, keep read and edit states on closely matched render paths instead of mixing shared button primitives with native text controls.
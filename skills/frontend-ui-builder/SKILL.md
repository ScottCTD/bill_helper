---
name: frontend-ui-builder
description: Build or evolve this repository's frontend UI without regressing interaction quality. Use when creating or changing layouts, dialogs, dashboards, agent/chat surfaces, overlays, forms, tables, or shared styling in `frontend/`.
---

# Frontend UI Builder

## Overview

This is the default frontend skill for this repository. It combines the durable lessons from the March 2026 redesign with the day-to-day workflow for building new UI, not just refactoring old UI.

Treat this as an evolving repo-specific frontend skill, not a static checklist. When a new convention, interaction pattern, or distilled UI behavior lands in the codebase and receives clear positive user feedback such as "nice work", "so good", or similar approval, update this skill so the pattern becomes reusable guidance instead of remaining one-off local knowledge.

## Use This Skill When

- You are building a new page, section, dialog, overlay, or form in `frontend/`.
- You are changing route-level layout, shared workspace chrome, or feature-module UI structure.
- You are touching the dashboard timeline, the agent workspace, or another surface with custom interaction behavior.
- You are moving styles between files or adding new rules under `frontend/src/styles/*`.

Do not use this skill for backend-only work or tiny copy-only changes that do not affect UI behavior, layout, or shared styling.

## Core Principles

1. Build from the shared product vocabulary first.
- Start with the existing layout primitives before inventing page-specific chrome:
  - `frontend/src/components/layout/PageHeader.tsx`
  - `frontend/src/components/layout/WorkspaceSection.tsx`
  - `frontend/src/components/layout/WorkspaceToolbar.tsx`
  - `frontend/src/components/layout/StatBlock.tsx`
- New pages should feel like part of the same product family unless there is a clear reason to diverge.

2. Treat scroll and overflow as architecture.
- Decide which surface owns scroll before styling the page.
- Dialogs should usually be fixed-height shells with internal scroll regions.
- Menus and dropdowns that can open inside cards, tables, or empty states should escape clipping through the shared floating positioning pattern.
- Sticky composers, sticky footers, and timeline rails are layout constraints, not polish.

3. Keep CSS ownership explicit.
- Use the current layer split:
  - `frontend/src/styles/tokens.css`
  - `frontend/src/styles/base.css`
  - `frontend/src/styles/shell.css`
  - `frontend/src/styles/workspaces.css`
  - `frontend/src/styles/dashboard.css`
  - `frontend/src/styles/overlays.css`
  - `frontend/src/styles/agent.css`
- Put rules where ownership is obvious. Do not regrow a single catch-all stylesheet.

4. Preserve valuable bespoke interactions.
- Shared systemization should simplify the codebase, not erase interactions that are materially better than a generic replacement.
- Before changing custom timeline behavior, agent chat geometry, or other high-touch UI, identify what must remain invariant.

5. Keep copy and density tight.
- Route and section descriptions should read like labels, not marketing blurbs.
- Prefer fewer containers and less text before adding visual decoration.

6. Agent/chat surfaces need stricter geometry than CRUD screens.
- Prevent bubble width shifts when nested content expands.
- Keep the composer docked to the bottom while the conversation pane owns scroll.
- Unify adjacent surfaces when the user perceives them as one control, such as the chat input and action row.

## Build Workflow

1. Classify the surface before editing.
- Decide whether the work is primarily:
  - route chrome
  - workspace/table/form UI
  - overlay or modal UI
  - dashboard visualization
  - agent/chat UI
- Start in the style layer and primitives that already own that surface.

2. Read the current behavior first.
- Inspect the touched component and the owning style file before editing.
- If the screen already has custom interaction behavior, note what must not regress.

3. Compose shared structure before local polish.
- Use the shared page primitives first.
- Only after structure is coherent should you tune spacing, colors, animation, or copy.

4. Make geometry explicit.
- For dialogs, define height, internal scroll regions, and sticky actions deliberately.
- For overlays, use the shared floating positioning patterns instead of hoping `overflow: visible` is enough.
- For chat-like views, set width and height constraints deliberately so nested UI does not reflow the conversation.

5. Audit the likely failure modes.
- Check for:
  - page scroll vs panel scroll
  - sticky elements losing their anchor
  - dropdown/menu clipping
  - animated elements jumping instead of transitioning
  - chat/timeline width instability
  - overlong helper copy
  - mismatched surfaces inside one control group

6. Verify both code and behavior.
- Run:
  - `npm run test`
  - `npm run build`
  - `uv run python scripts/check_docs_sync.py`
- For high-touch UI, do browser QA on:
  - timeline motion
  - sticky footers/composers
  - empty states with open menus
  - modal internal scrolling
  - desktop and mobile breakpoints

7. Feed validated lessons back into the skill.
- If the work introduced a frontend convention or behavior pattern that the user explicitly liked, update this skill in the same workstream or the next closely related one.
- Add only durable guidance that generalizes across more than one screen or feature.
- Do not add every preference verbatim; distill the underlying rule so future frontend work can reuse it.

## Decision Rules

- If you must choose, preserve interaction correctness before visual flourish.
- If a screen feels wordy, delete copy before adding more containers.
- If a component depends on ancestor overflow behavior, the ownership boundary is probably wrong.
- If an interaction is already good and distinctive, preserve it and refactor around it instead of normalizing it away.

## Definition of Done

- Shared chrome or styling ownership is clearer after the change, not more scattered.
- Scroll ownership is explicit and stable.
- Menus and dialogs do not clip or trigger page scroll regressions.
- High-value custom interactions still feel intentional.
- Copy is tighter than before.
- Tests, build, and docs sync all pass.

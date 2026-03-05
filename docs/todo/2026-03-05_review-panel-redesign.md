# Agent Review Panel Redesign — Flash Card + Table of Contents

## Summary

Redesign the agent review panel from a linear scrolling list into a focused flash-card experience with a sidebar table of contents. The new layout shows one proposal at a time, supports structured inline editing for all change types, and adds a thread-level review entry point.

## Motivation

The current `AgentRunReviewModal` displays all proposals in a flat scrollable dialog. This makes it hard to focus on individual proposals, navigate between them, or edit proposals with structured forms. The linear layout lacks orientation (no TOC) and editing is limited to raw JSON overrides for entry creates only.

## Design

### Layout

- **Two-column modal**: Left sidebar (Table of Contents) + right main area (single flash card).
- Only one proposal is visible at a time in the main area.
- TOC sidebar lists all proposals with short summaries and status badges.
- Batch actions (Approve All / Reject All) live at the TOC sidebar level, not per-card.

### Table of Contents

Each proposal row shows a short summary line based on change type:

- **Entry**: `Create Entry: {name} on {date}` / `Update Entry: {selector.name}` / `Delete Entry: {selector.name}`
- **Tag**: `Create Tag: {name}` / `Update Tag: {name}` / `Delete Tag: {name}`
- **Entity**: `Create Entity: {name}` / `Update Entity: {name}` / `Delete Entity: {name}`

Visual indicators: change type color accent, status badge, pending vs resolved dimming. Click to jump.

### Flash Card

Each card displays:

- Change type label + status badge
- Agent's rationale text
- Diff preview (reusing existing `buildProposalDiff` engine)
- Metadata pills (target, selector, impact preview)
- Inline structured editor (when applicable)

### Controls

- **Per-card actions**: Approve / Reject (in the card footer area)
- **Batch actions**: Approve All / Reject All (in the TOC sidebar)
- **Auto-advance**: After approve/reject, focus moves to the next pending card
- **Keyboard shortcuts**: `A` = approve, `R` = reject, `→`/`Space` = next, `←` = previous
- **Skip**: Move to next pending without acting

### Card Transitions

Subtle slide/fade animation when navigating between cards.

### Entry Point

- **Primary**: Always-visible "Review" button in the agent panel header (left of "New Thread"). Opens review modal for all pending proposals across the entire thread.
- **Secondary**: Per-run review link in `AgentRunBlock` (kept as fallback).

### Inline Editing

#### Entry proposals (create/update)

Structured form modeled on `EntryEditorModal`: kind, date, name, amount, currency, from_entity, to_entity, tags, markdown_notes. For update proposals, the full merged entry is editable (not just patch fields). Form state diff builds `payload_override`.

#### Tag proposals (create/update)

Simple inline form: name, type. Pre-populated from `payload_json`.

#### Entity proposals (create/update)

Simple inline form: name, category. Pre-populated from `payload_json`.

#### Delete proposals

Read-only full field snapshot for confirmation. No editing.

### Backend Changes

- Expand `payload_override` support in `review.py` to cover `create_tag`, `update_tag`, `create_entity`, `update_entity` (currently only entry types).
- Enhance review results prefix in `message_history.py` to include actual changed field values when user edits are present.

### Edit Priority

User edits are always preserved and take top priority. "Approve All" uses edited `payload_override` where edits exist, original payloads otherwise.

## Affected Files

### Frontend

- `frontend/src/components/agent/review/AgentRunReviewModal.tsx` — major rewrite
- `frontend/src/components/agent/review/` — new: `ReviewTableOfContents.tsx`, inline editor components
- `frontend/src/components/agent/AgentPanel.tsx` — thread-level review button, updated review modal integration
- `frontend/src/components/agent/AgentRunBlock.tsx` — minor: keep as secondary entry point
- `frontend/src/styles.css` — new flash card + TOC styles

### Backend

- `backend/services/agent/review.py` — expand `payload_override` allowed types
- `backend/services/agent/message_history.py` — richer review prefix with edit values

### Documentation

- `docs/frontend.md` — review panel architecture
- `docs/backend.md` — expanded payload_override
- `docs/api.md` — if API changes needed

## Tasks

1. Build Table of Contents sidebar component
2. Refactor modal to flash card two-column layout
3. Flash card transition animations
4. Action bar redesign (per-card + batch at TOC level)
5. CSS for flash card + TOC layout
6. Thread-level review button in agent panel header
7. Inline entry editor for flash cards
8. Inline tag/entity editor for flash cards
9. Backend: expand payload_override support
10. Backend: richer review prefix with edit values
11. Documentation updates
12. Tests

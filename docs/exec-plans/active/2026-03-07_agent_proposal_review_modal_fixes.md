# Agent Proposal Review Modal Fixes

**Created:** 2026-03-07

## Overview

Refine the agent proposal review modal UI based on UX feedback.

## Changes Required

### 1. Move Control Buttons to Top (Spanning Both Columns)

Currently, the control buttons (Approve All / Reject All, Previous, Next, Skip, Reject, Approve) are located at the bottom of the card in [`agent-review-card-footer`](frontend/src/features/agent/review/AgentThreadReviewModal.tsx). Move them to appear above the card content and spanning both columns (sidebar and card area). Preferably in the header of the modal (below title).

- **Location:** [`AgentThreadReviewModal.tsx`](frontend/src/features/agent/review/AgentThreadReviewModal.tsx)
- **Current:** `<footer className="agent-review-card-footer">`
- **Target:** Move buttons to a new controls bar that spans both columns (between sidebar and card), sharing the same horizontal area as Approve All/Reject All buttons
- **CSS:** Added `.agent-review-controls-bar` with `col-span-2` in [`styles.css`](frontend/src/styles.css)

### 2. Widen Modal to Near Full Page

The two-column modal needs more horizontal space.

### 3. Remove "PENDING_REVIEW" Status Badge from Left Column

Each entry in the left column sidebar shows a status badge with "PENDING_REVIEW" which is redundant since entries are already categorized into "Pending" and "Reviewed / Failed" sections.

### 4. Remove Redundant Description Text

The sidebar contains redundant explanatory text that should be removed.

- **Location:** [`AgentThreadReviewModal.tsx`](frontend/src/features/agent/review/AgentThreadReviewModal.tsx)
- **Current:** `<p>Review proposals across the whole thread. Pending items stay first; resolved items remain available for audit.</p>`
- **Target:** Remove this paragraph element entirely

## Notes

- The sidebar sections "Pending" and "Reviewed / Failed" already provide sufficient context
- Moving buttons to top allows users to navigate/act before reading the full proposal
- The controls bar now spans both columns for better visibility and usability
- Modal width increased to closer to full-page width for more horizontal space


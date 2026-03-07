# Agent Proposal Review Modal Fixes

**Created:** 2026-03-07

## Overview

Refine the agent proposal review modal UI based on UX feedback.

## Changes Required

### 1. Move Control Buttons to Top

Currently, the control buttons (Previous, Next, Skip, Reject, Approve) are located at the bottom of the card in [`agent-review-card-footer`](frontend/src/features/agent/review/AgentThreadReviewModal.tsx:936-979). Move them to appear above the card content instead.

- **Location:** [`AgentThreadReviewModal.tsx`](frontend/src/features/agent/review/AgentThreadReviewModal.tsx:936-979)
- **Current:** `<footer className="agent-review-card-footer">`
- **Target:** Move buttons to header section of the card

### 2. Widen Modal Horizontally

The two-column modal needs more horizontal space. Current max-width is `max-w-7xl` at line 1459 in [`styles.css`](frontend/src/styles.css:1459).

- **Location:** [`styles.css:1459`](frontend/src/styles.css:1459)
- **Current:** `max-w-7xl`
- **Target:** Increase to `max-w-[90vw]` or similar wider width

### 3. Remove "PENDING_REVIEW" Status Badge from Left Column

Each entry in the left column sidebar shows a status badge with "PENDING_REVIEW" which is redundant since entries are already categorized into "Pending" and "Reviewed / Failed" sections.

- **Location:** [`ReviewTocSection`](frontend/src/features/agent/review/AgentThreadReviewModal.tsx:157-208), specifically line 199-201
- **Current:** Shows `{reviewItem.item.status}` badge for each item
- **Target:** Remove the status badge from the sidebar list items

### 4. Remove Redundant Description Text

The sidebar contains redundant explanatory text that should be removed.

- **Location:** [`AgentThreadReviewModal.tsx:720`](frontend/src/features/agent/review/AgentThreadReviewModal.tsx:720)
- **Current:** `<p>Review proposals across the whole thread. Pending items stay first; resolved items remain available for audit.</p>`
- **Target:** Remove this paragraph element entirely

## Affected Files

| File | Changes |
|------|---------|
| `frontend/src/features/agent/review/AgentThreadReviewModal.tsx` | Move buttons, remove status badge in sidebar, remove description text |
| `frontend/src/styles.css` | Increase modal max-width |

## Notes

- The sidebar sections "Pending" and "Reviewed / Failed" already provide sufficient context
- Moving buttons to top allows users to navigate/act before reading the full proposal
- The modal already has `max-w-[96vw]` on line 1951 for some contexts - verify appropriate width is used

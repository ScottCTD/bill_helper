# Running Thread Status Indicator

## Problem

When an agent run is active, there is no visual indication in the thread list sidebar. Users cannot easily see which threads have ongoing runs when switching between threads.

## Current State

- The backend continues processing even when the user switches tabs
- The frontend polls for updates every 5 seconds when a thread has an active run
- The `AgentThreadList` component receives threads but does not show running status per thread

## Proposed Solution

Add a subtle, modern spinner/indicator overlay on thread buttons in the sidebar when they have an active running status.

### UX Requirements

1. **Visual indicator**: A small spinner (loading icon) positioned on or beside the thread button
2. **Non-intrusive**: Should not dominate the thread name or clutter the interface
3. **Accessible**: Include aria-label indicating "Thread is processing"
4. **Animation**: Smooth, subtle animation (CSS-based, performant)

### Implementation Notes

The thread list already receives thread data that includes run information. The indicator should:

- Show when any run in the thread has `status === "running"`
- Be positioned to not overlap the thread name significantly
- Use existing Lucide icons (e.g., `Loader2`) with CSS animation
- Follow the existing styling conventions (`.agent-thread-row`, `.agent-thread-button`)

### Affected Files

- `frontend/src/components/agent/panel/AgentThreadList.tsx`
- `frontend/src/components/agent/panel/AgentThreadList.css` (or add styles to existing CSS)

### Related Code

- `AgentPanel.tsx` line 257-269: Logic for detecting `hasActiveRun` and `activeRunId`
- `AgentPanel.tsx` line 138-144: Polling interval setup for running runs

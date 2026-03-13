# Parallel Agent Thread UX Follow-Up

## Summary

The backend already supports multiple agent threads running at the same time, but the current frontend only exposes that capability partially. The thread list can show background activity, yet the composer and thread controls still behave as if one active send should lock the whole panel.

This task should make the thread experience honestly reflect parallel execution instead of implying a single-active-thread model.

## User Problem

The main reported scenario is:

1. Start a run in thread 1.
2. Create or switch to thread 2 while thread 1 is still running.
3. The composer in thread 2 still behaves like the active action is `Stop` instead of `Send`.

That makes it unclear whether thread 2 can start its own run before thread 1 finishes, and it raises a more serious trust issue: the UI suggests that controls may still be targeting the old thread even after the user has switched context.

## Current Behaviors

Based on code inspection, the current frontend behavior is:

- A run in one thread does continue in the background after the user switches to another thread.
- The thread list can continue showing that a background thread is running.
- Creating a new thread while another thread is running is allowed.
- After switching to a different idle thread during an in-flight streamed send, the composer can still show `Stop` instead of `Send`.
- While that earlier send remains open, the panel can behave as though the newly selected thread is also "in flight" even when it has no run of its own.
- The UI therefore communicates a stronger lock than the backend actually enforces.
- Some unrelated controls remain disabled more broadly than necessary while any in-flight send is open.
- The result is that parallel execution exists at the system level, but the user-facing interaction model is still partly serialized.

## Cause Summary

Based on code inspection, the root problem is not the backend run model. The issue is that the frontend currently mixes two different notions of activity:

- thread-specific running state for the currently selected thread
- panel-global sending and streaming state for whichever request was started most recently

Because those two scopes are blended together:

- switching thread selection does not fully switch the composer into the new thread's context
- the primary action can stay in a stop-oriented state even on an idle thread
- control lockouts can apply across the panel instead of only where they are actually needed
- the UI can leave users unsure which thread a stop action would affect

## Intended Behaviors

The intended frontend behavior should be:

- Each thread's running state is represented independently.
- Switching to an idle thread immediately restores that thread's normal composer state.
- The composer should show `Send` for an idle selected thread even if another thread keeps running in the background.
- The composer should show `Stop` only when the selected thread itself has a run that can be interrupted.
- Starting thread 2 while thread 1 is still running should be a normal supported flow, not a visually ambiguous edge case.
- Background-running threads should remain visibly marked in the thread list.
- Thread actions should only be disabled when the specific target thread or specific pending mutation requires it.
- The overall UI should make it obvious that "multiple threads may run at once" is a supported behavior.

## Related Risks To Check

This task should also verify and fix any adjacent issues caused by the same state-model mismatch, especially:

- stop actions targeting the wrong thread after a thread switch
- thread rename or delete controls being disabled for unrelated idle threads
- composer mode toggles or launch affordances being blocked unnecessarily by activity in another thread
- stale or misleading activity state after creating a fresh thread during an existing run

## Scope

This work item should cover:

- making composer action selection thread-scoped instead of panel-global
- making stop behavior unambiguously target the selected thread only
- reducing over-broad UI lockouts caused by background activity in other threads
- preserving visible background running indicators in the thread list
- adding regression coverage for thread switching during active runs

## Non-Goals

- changing the backend execution model for agent runs
- redesigning the overall agent workspace layout
- changing the review workflow or proposal model
- changing bulk-mode semantics beyond any directly related state-isolation bugs

## Acceptance Criteria

- When thread 1 is running and the user switches to an idle thread 2, the composer in thread 2 shows `Send`, not `Stop`.
- The user can submit a new message in thread 2 while thread 1 continues running.
- Stopping a run from the currently selected thread never interrupts a different thread's run.
- Background-running threads remain visibly marked in the thread list.
- Idle threads do not lose rename or delete affordances solely because another thread is running.
- The UI no longer implies that the whole agent panel is locked to one active thread at a time.

## Verification Expectations

For the eventual implementation, verify with:

- targeted frontend tests for thread switching, second-thread send, and stop-target correctness
- any broader frontend regression checks needed for the agent panel
- `uv run python scripts/check_docs_sync.py`

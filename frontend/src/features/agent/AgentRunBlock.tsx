/**
 * CALLING SPEC:
 * - Purpose: render per-run agent UI — activity (delegated) plus optional change-item summary.
 * - Inputs: callers that import `frontend/src/features/agent/AgentRunBlock.tsx`.
 * - Outputs: `AgentRunBlock` React component.
 * - Side effects: React rendering.
 */
import { useMemo } from "react";

import type { AgentRun, AgentRunEvent, AgentToolCall } from "../../lib/types";
import { cn } from "../../lib/utils";
import {
  buildRunTimelineFromEvents,
  mergeRunEvents,
  mergeRunToolCalls,
  summarizeRunChangeTypes
} from "./activity";
import { AssistantMessageRunWork } from "./AssistantMessageRunWork";

interface AgentRunBlockProps {
  run: AgentRun;
  onInspectActivity?: () => void;
  onHydrateToolCall?: (runId: string, toolCallId: string) => void;
  hydratingToolCallIds?: ReadonlySet<string>;
  mode?: "activity" | "summary" | "all";
  optimisticEvents?: AgentRunEvent[];
  optimisticToolCalls?: AgentToolCall[];
  streamingReasoningText?: string;
}

export function AgentRunBlock({
  run,
  onInspectActivity,
  onHydrateToolCall,
  hydratingToolCallIds,
  mode = "all",
  optimisticEvents = [],
  optimisticToolCalls = [],
  streamingReasoningText = ""
}: AgentRunBlockProps) {
  const showActivity = mode !== "summary";
  const showSummary = mode !== "activity";
  const hasSummaryChanges = showSummary && run.change_items.length > 0;
  const pendingCount = run.change_items.filter((item) => item.status === "PENDING_REVIEW").length;
  const failedCount = run.change_items.filter((item) => item.status === "APPLY_FAILED").length;
  const typeSummary = summarizeRunChangeTypes(run.change_items);

  const optimisticRunEventsByRunId = useMemo(
    () => ({ [run.id]: optimisticEvents }),
    [run.id, optimisticEvents]
  );
  const optimisticToolCallsByRunId = useMemo(
    () => ({ [run.id]: optimisticToolCalls }),
    [run.id, optimisticToolCalls]
  );

  const mergedEvents = useMemo(() => mergeRunEvents(run.events, optimisticEvents), [run.events, optimisticEvents]);
  const mergedToolCalls = useMemo(
    () => mergeRunToolCalls(run.tool_calls, optimisticToolCalls),
    [run.tool_calls, optimisticToolCalls]
  );
  const activityTimeline = useMemo(
    () => buildRunTimelineFromEvents(mergedEvents, mergedToolCalls),
    [mergedEvents, mergedToolCalls]
  );
  const hasActivitySignals =
    Boolean(run.error_text) ||
    activityTimeline.length > 0 ||
    streamingReasoningText.length > 0 ||
    run.status === "running";

  if (!hasActivitySignals && !hasSummaryChanges) {
    return null;
  }

  return (
    <div className={cn("agent-run-block", showSummary && "agent-run-block-summary")}>
      {showActivity && hasActivitySignals ? (
        <AssistantMessageRunWork
          runs={[run]}
          optimisticRunEventsByRunId={optimisticRunEventsByRunId}
          optimisticToolCallsByRunId={optimisticToolCallsByRunId}
          streamingReasoningText={streamingReasoningText}
          onInspectActivity={onInspectActivity}
          onHydrateToolCall={onHydrateToolCall}
          hydratingToolCallIds={hydratingToolCallIds}
        />
      ) : null}

      {hasSummaryChanges ? (
        <div className="agent-run-changes-summary">
          <h4>{pendingCount > 0 ? `${pendingCount} proposed changes pending review` : "No pending changes in this run"}</h4>
          <p className="muted">
            {pendingCount > 0
              ? "Use the thread header Review button to process proposals."
              : "Reviewed changes remain available from the thread header Review button."}
          </p>
          <div className="agent-run-change-chips">
            <span className="agent-run-change-chip">Entry x{typeSummary.entryCount}</span>
            <span className="agent-run-change-chip">Group x{typeSummary.groupCount}</span>
            <span className="agent-run-change-chip">Tag x{typeSummary.tagCount}</span>
            <span className="agent-run-change-chip">Entity x{typeSummary.entityCount}</span>
          </div>
          {failedCount > 0 ? (
            <p className="error">
              {failedCount} apply failure{failedCount === 1 ? "" : "s"} detected. Open review for details.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

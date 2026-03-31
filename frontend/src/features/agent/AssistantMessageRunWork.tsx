/**
 * CALLING SPEC:
 * - Purpose: render merged agent run work for one assistant turn — flat stream while running, collapsible separator when completed.
 * - Inputs: callers that import `frontend/src/features/agent/AssistantMessageRunWork.tsx`.
 * - Outputs: `AssistantMessageRunWork` React component.
 * - Side effects: local expand/collapse state; optional `onInspectActivity` on separator toggle.
 */
import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import type { AgentRun, AgentRunEvent, AgentToolCall } from "../../lib/types";
import { cn } from "../../lib/utils";
import { buildAgentWorkSeparatorLabel, mergeRunActivityItems } from "./activity";
import { AgentRunActivityRows } from "./AgentRunActivity";

export interface AssistantMessageRunWorkProps {
  runs: AgentRun[];
  optimisticRunEventsByRunId: Record<string, AgentRunEvent[]>;
  optimisticToolCallsByRunId: Record<string, AgentToolCall[]>;
  streamingReasoningText?: string;
  onInspectActivity?: () => void;
  onHydrateToolCall?: (runId: string, toolCallId: string) => void;
  hydratingToolCallIds?: ReadonlySet<string>;
}

export function AssistantMessageRunWork({
  runs,
  optimisticRunEventsByRunId,
  optimisticToolCallsByRunId,
  streamingReasoningText = "",
  onInspectActivity,
  onHydrateToolCall,
  hydratingToolCallIds
}: AssistantMessageRunWorkProps) {
  const [expanded, setExpanded] = useState(false);

  const mergedItems = useMemo(
    () =>
      mergeRunActivityItems(runs, (runId) => ({
        events: optimisticRunEventsByRunId[runId] ?? [],
        toolCalls: optimisticToolCallsByRunId[runId] ?? []
      })),
    [runs, optimisticRunEventsByRunId, optimisticToolCallsByRunId]
  );

  const hasStreamingReasoningText = streamingReasoningText.trim().length > 0;
  const anyRunning = runs.some((run) => run.status === "running");
  /** Flat stream only while the run is in flight or reasoning is still streaming. */
  const isLive = anyRunning || hasStreamingReasoningText;

  /** Running turn with no timeline rows yet (waiting for first event or interleaved empty state). */
  const placeholderActive =
    anyRunning && mergedItems.length === 0 && !hasStreamingReasoningText;

  const hasRenderableActivity =
    mergedItems.length > 0 || hasStreamingReasoningText || placeholderActive;

  const separatorLabel = useMemo(
    () => buildAgentWorkSeparatorLabel(runs, mergedItems),
    [runs, mergedItems]
  );

  const showCompletedChrome = !isLive && hasRenderableActivity;

  const errorNodes = runs.map((run) =>
    run.error_text ? (
      <p key={run.id} className="error">
        {run.error_text}
      </p>
    ) : null
  );

  if (!hasRenderableActivity && !errorNodes.some(Boolean)) {
    return null;
  }

  if (isLive) {
    return (
      <div className="agent-assistant-run-work">
        {errorNodes}
        <AgentRunActivityRows
          items={mergedItems}
          onInspectActivity={onInspectActivity}
          onHydrateToolCall={onHydrateToolCall}
          hydratingToolCallIds={hydratingToolCallIds}
          streamingReasoningText={streamingReasoningText}
          showStreamingPlaceholder={placeholderActive}
        />
      </div>
    );
  }

  return (
    <div className="agent-assistant-run-work">
      {errorNodes}
      {showCompletedChrome ? (
        <>
          {expanded ? (
            <AgentRunActivityRows
              items={mergedItems}
              onInspectActivity={onInspectActivity}
              onHydrateToolCall={onHydrateToolCall}
              hydratingToolCallIds={hydratingToolCallIds}
            />
          ) : null}
          <button
            type="button"
            className={cn("agent-work-separator", expanded && "agent-work-separator-expanded")}
            aria-expanded={expanded}
            onClick={() => {
              setExpanded((value) => !value);
              onInspectActivity?.();
            }}
          >
            <span className="agent-work-separator-line" aria-hidden />
            <span className="agent-work-separator-center">
              <span className="agent-work-separator-label">{separatorLabel}</span>
              {expanded ? (
                <ChevronUp className="agent-work-separator-chevron h-4 w-4 shrink-0" aria-hidden />
              ) : (
                <ChevronDown className="agent-work-separator-chevron h-4 w-4 shrink-0" aria-hidden />
              )}
            </span>
            <span className="agent-work-separator-line" aria-hidden />
          </button>
        </>
      ) : null}
    </div>
  );
}

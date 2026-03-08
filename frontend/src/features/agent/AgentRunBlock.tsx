import { useEffect, useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";

import type { AgentRun, AgentRunEvent, AgentToolCall } from "../../lib/types";
import { cn } from "../../lib/utils";
import {
  buildRunTimelineFromEvents,
  isToolLifecycleTerminal,
  mergeRunEvents,
  mergeRunToolCalls,
  reasoningSourceLabel,
  reasoningUpdatePreview,
  summarizeActivityTimeline,
  summarizeRunChangeTypes,
  toolLifecycleLabel,
  type ReasoningUpdateSource,
  type RunActivityItem
} from "./activity";
import { MarkdownRenderer } from "../../components/ui/MarkdownRenderer";

interface AgentRunBlockProps {
  run: AgentRun;
  isMutating: boolean;
  onHydrateToolCall?: (runId: string, toolCallId: string) => void;
  hydratingToolCallIds?: ReadonlySet<string>;
  mode?: "activity" | "summary" | "all";
  optimisticEvents?: AgentRunEvent[];
  optimisticToolCalls?: AgentToolCall[];
  streamingReasoningText?: string;
  streamingAssistantText?: string;
}

const STREAMING_ASSISTANT_PLACEHOLDER = "\u258d";

function prettyDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function renderableStreamingUpdateText(value: string, showPlaceholder: boolean): string {
  if (value.length > 0) {
    return value.trim().length > 0 ? value : STREAMING_ASSISTANT_PLACEHOLDER;
  }
  return showPlaceholder ? STREAMING_ASSISTANT_PLACEHOLDER : "";
}

function CollapsibleReasoningUpdate({
  message,
  source,
  defaultOpen
}: {
  message: string;
  source: ReasoningUpdateSource;
  defaultOpen?: boolean;
}) {
  const label = reasoningSourceLabel(source);
  return (
    <details className="agent-reasoning-update-collapsible" open={defaultOpen}>
      <summary>
        <ChevronRight className="agent-tool-call-chevron" />
        <span className="agent-reasoning-update-label">{label}</span>
        <span className="agent-reasoning-update-preview">{reasoningUpdatePreview(message)}</span>
      </summary>
      <MarkdownRenderer markdown={message} className="agent-run-reasoning-update" />
    </details>
  );
}

function ToolCallTimelineRow({
  item,
  defaultOpen,
  onHydrateToolCall,
  isHydrating = false
}: {
  item: Extract<RunActivityItem, { type: "tool_call" }>;
  defaultOpen?: boolean;
  onHydrateToolCall?: (runId: string, toolCallId: string) => void;
  isHydrating?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(Boolean(defaultOpen));
  const toolCall = item.toolCall;
  const lifecycleLabel = toolLifecycleLabel(item.lifecycleEventType);
  const hasSnapshot = toolCall !== null;
  const hasFullPayload = Boolean(toolCall?.has_full_payload);
  const shouldHydrate = isOpen && !hasFullPayload;
  const showTerminalOutput = hasFullPayload && isToolLifecycleTerminal(item.lifecycleEventType);

  useEffect(() => {
    if (!shouldHydrate) {
      return;
    }
    if (!onHydrateToolCall) {
      return;
    }
    onHydrateToolCall(item.runId, item.toolCallId);
  }, [item.runId, item.toolCallId, onHydrateToolCall, shouldHydrate]);

  return (
    <details
      className={cn("agent-tool-call", !hasSnapshot && "agent-tool-call-static")}
      open={defaultOpen}
      onToggle={(event) => setIsOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary>
        <ChevronRight className="agent-tool-call-chevron" />
        <span className="agent-tool-call-name">{toolCall?.tool_name ?? "Tool call"}</span>
        <span className="agent-tool-call-status">{lifecycleLabel}</span>
        <span className="agent-tool-call-time muted">
          {prettyDateTime(item.createdAt)}
        </span>
      </summary>
      {isOpen ? (
        <div className="agent-tool-call-details">
          {!hasSnapshot ? (
            <>
              <p className="agent-tool-call-details-label">Tool</p>
              <p className="muted agent-tool-call-pending-detail">
                {isHydrating ? "Loading tool snapshot..." : "Waiting for tool snapshot..."}
              </p>
              <pre>{JSON.stringify({ tool_call_id: item.toolCallId }, null, 2)}</pre>
            </>
          ) : !hasFullPayload ? (
            <>
              <p className="agent-tool-call-details-label">Tool details</p>
              <p className="muted agent-tool-call-pending-detail">
                {isHydrating ? "Loading tool call details..." : "Loading on demand..."}
              </p>
              <pre>{JSON.stringify({ tool_call_id: item.toolCallId }, null, 2)}</pre>
            </>
          ) : (
            <>
              <p className="agent-tool-call-details-label">Arguments</p>
              <pre className="agent-tool-call-arguments">{JSON.stringify(toolCall.input_json, null, 2)}</pre>
              {showTerminalOutput ? (
                <>
                  <p className="agent-tool-call-details-label">Model-visible tool result</p>
                  <pre className="agent-tool-call-output">{toolCall.output_text || "(empty)"}</pre>
                  <details>
                    <summary className="agent-tool-call-details-label">Structured output (debug)</summary>
                    <pre>{JSON.stringify(toolCall.output_json, null, 2)}</pre>
                  </details>
                </>
              ) : (
                <p className="muted agent-tool-call-pending-detail">Waiting for tool result...</p>
              )}
            </>
          )}
        </div>
      ) : null}
    </details>
  );
}

function ActivityTimeline({
  items,
  isRunning,
  onHydrateToolCall,
  hydratingToolCallIds,
  streamingReasoningText = "",
  streamingAssistantText = "",
  showStreamingPlaceholder = false
}: {
  items: RunActivityItem[];
  isRunning: boolean;
  onHydrateToolCall?: (runId: string, toolCallId: string) => void;
  hydratingToolCallIds?: ReadonlySet<string>;
  streamingReasoningText?: string;
  streamingAssistantText?: string;
  showStreamingPlaceholder?: boolean;
}) {
  const visibleStreamingReasoningText = renderableStreamingUpdateText(
    streamingReasoningText,
    false
  );
  const visibleStreamingAssistantText = renderableStreamingUpdateText(
    streamingAssistantText,
    showStreamingPlaceholder
  );
  const hasStreamingReasoningText = visibleStreamingReasoningText.length > 0;
  const hasStreamingAssistantText = visibleStreamingAssistantText.length > 0;
  return (
    <details className={cn("agent-run-root-activity", isRunning && "agent-run-root-activity-static")} open={isRunning}>
      <summary>
        <ChevronRight className="agent-tool-call-chevron" />
        <span className="agent-tool-call-group-label">
          {summarizeActivityTimeline(
            items,
            (hasStreamingReasoningText ? 1 : 0) + (hasStreamingAssistantText ? 1 : 0)
          )}
        </span>
        {isRunning ? <span className="agent-tool-call-status">live</span> : null}
      </summary>
      <div className="agent-run-activity-timeline">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          if (item.type === "reasoning_update") {
            return (
              <CollapsibleReasoningUpdate
                key={item.key}
                message={item.message}
                source={item.source}
                defaultOpen={isRunning && isLast}
              />
            );
          }
          return (
            <ToolCallTimelineRow
              key={item.key}
              item={item}
              defaultOpen={false}
              onHydrateToolCall={onHydrateToolCall}
              isHydrating={Boolean(hydratingToolCallIds?.has(item.toolCallId))}
            />
          );
        })}
        {hasStreamingReasoningText ? (
          <CollapsibleReasoningUpdate
            message={visibleStreamingReasoningText}
            source="model_reasoning"
            defaultOpen={isRunning}
          />
        ) : null}
        {hasStreamingAssistantText ? (
          <CollapsibleReasoningUpdate
            message={visibleStreamingAssistantText}
            source="assistant_content"
            defaultOpen={isRunning}
          />
        ) : null}
      </div>
    </details>
  );
}

export function PendingAssistantActivityBlock({
  events,
  toolCalls = [],
  onHydrateToolCall,
  hydratingToolCallIds,
  streamingReasoningText = "",
  streamingAssistantText = ""
}: {
  events: AgentRunEvent[];
  toolCalls?: AgentToolCall[];
  onHydrateToolCall?: (runId: string, toolCallId: string) => void;
  hydratingToolCallIds?: ReadonlySet<string>;
  streamingReasoningText?: string;
  streamingAssistantText?: string;
}) {
  const items = useMemo(() => buildRunTimelineFromEvents(events, toolCalls), [events, toolCalls]);
  const hasStreamingReasoningText = streamingReasoningText.length > 0;
  const hasStreamingAssistantText = streamingAssistantText.length > 0;
  const showStreamingPlaceholder =
    events.length > 0 &&
    items.length === 0 &&
    !hasStreamingReasoningText &&
    !hasStreamingAssistantText;

  if (items.length === 0 && !hasStreamingReasoningText && !hasStreamingAssistantText && !showStreamingPlaceholder) {
    return null;
  }

  return (
    <ActivityTimeline
      items={items}
      isRunning={true}
      onHydrateToolCall={onHydrateToolCall}
      hydratingToolCallIds={hydratingToolCallIds}
      streamingReasoningText={streamingReasoningText}
      streamingAssistantText={streamingAssistantText}
      showStreamingPlaceholder={showStreamingPlaceholder}
    />
  );
}

export function AgentRunBlock({
  run,
  isMutating,
  onHydrateToolCall,
  hydratingToolCallIds,
  mode = "all",
  optimisticEvents = [],
  optimisticToolCalls = [],
  streamingReasoningText = "",
  streamingAssistantText = ""
}: AgentRunBlockProps) {
  const showActivity = mode !== "summary";
  const showSummary = mode !== "activity";
  const hasSummaryChanges = showSummary && run.change_items.length > 0;
  const pendingCount = run.change_items.filter((item) => item.status === "PENDING_REVIEW").length;
  const failedCount = run.change_items.filter((item) => item.status === "APPLY_FAILED").length;
  const typeSummary = summarizeRunChangeTypes(run.change_items);
  const mergedEvents = useMemo(() => mergeRunEvents(run.events, optimisticEvents), [run.events, optimisticEvents]);
  const mergedToolCalls = useMemo(
    () => mergeRunToolCalls(run.tool_calls, optimisticToolCalls),
    [run.tool_calls, optimisticToolCalls]
  );
  const activityTimeline = useMemo(
    () => buildRunTimelineFromEvents(mergedEvents, mergedToolCalls),
    [mergedEvents, mergedToolCalls]
  );
  const hasStreamingReasoningText = streamingReasoningText.length > 0;
  const hasStreamingAssistantText = streamingAssistantText.length > 0;
  const isRunning = run.status === "running";
  const showStreamingPlaceholder =
    isRunning &&
    mergedEvents.length > 0 &&
    activityTimeline.length === 0 &&
    !hasStreamingReasoningText &&
    !hasStreamingAssistantText;
  const hasActivityContent =
    Boolean(run.error_text) ||
    activityTimeline.length > 0 ||
    hasStreamingReasoningText ||
    hasStreamingAssistantText ||
    showStreamingPlaceholder;

  if (!hasActivityContent && !hasSummaryChanges) {
    return null;
  }

  return (
    <div className={cn("agent-run-block", showSummary && "agent-run-block-summary")}>
      {showActivity ? (
        <>
          {run.error_text ? <p className="error">{run.error_text}</p> : null}
          {hasActivityContent ? (
            <ActivityTimeline
              items={activityTimeline}
              isRunning={isRunning}
              onHydrateToolCall={onHydrateToolCall}
              hydratingToolCallIds={hydratingToolCallIds}
              streamingReasoningText={streamingReasoningText}
              streamingAssistantText={streamingAssistantText}
              showStreamingPlaceholder={showStreamingPlaceholder}
            />
          ) : null}
        </>
      ) : null}

      {hasSummaryChanges ? (
        <div className="agent-run-changes-summary">
          <h4>{pendingCount > 0 ? `${pendingCount} proposed changes pending review` : "No pending changes in this run"}</h4>
          <p className="muted">
            {pendingCount > 0 ? "Use the thread header Review button to process proposals." : "Reviewed changes remain available from the thread header Review button."}
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

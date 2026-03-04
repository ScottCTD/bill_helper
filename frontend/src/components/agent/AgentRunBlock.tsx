import { useMemo } from "react";
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
import { Button } from "../ui/button";
import { MarkdownRenderer } from "../ui/MarkdownRenderer";

interface AgentRunBlockProps {
  run: AgentRun;
  isMutating: boolean;
  onReviewRun: (runId: string) => void;
  mode?: "activity" | "summary" | "all";
  optimisticEvents?: AgentRunEvent[];
  optimisticToolCalls?: AgentToolCall[];
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

function renderableStreamingAssistantText(value: string, showPlaceholder: boolean): string {
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
  defaultOpen
}: {
  item: Extract<RunActivityItem, { type: "tool_call" }>;
  defaultOpen?: boolean;
}) {
  const toolCall = item.toolCall;
  const lifecycleLabel = toolLifecycleLabel(item.lifecycleEventType);
  const hasDetails = toolCall !== null;
  const showTerminalOutput = toolCall !== null && isToolLifecycleTerminal(item.lifecycleEventType);

  return (
    <details className={cn("agent-tool-call", !hasDetails && "agent-tool-call-static")} open={defaultOpen}>
      <summary>
        <ChevronRight className="agent-tool-call-chevron" />
        <span className="agent-tool-call-name">{toolCall?.tool_name ?? "Tool call"}</span>
        <span className="agent-tool-call-status">{lifecycleLabel}</span>
        <span className="agent-tool-call-time muted">
          {prettyDateTime(item.createdAt)}
        </span>
      </summary>
      <div className="agent-tool-call-details">
        {toolCall ? (
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
        ) : (
          <>
            <p className="agent-tool-call-details-label">Tool</p>
            <p className="muted agent-tool-call-pending-detail">Waiting for tool snapshot...</p>
            <pre>{JSON.stringify({ tool_call_id: item.toolCallId }, null, 2)}</pre>
          </>
        )}
      </div>
    </details>
  );
}

function ActivityTimeline({
  items,
  isRunning,
  streamingAssistantText = "",
  showStreamingAssistantPlaceholder = false
}: {
  items: RunActivityItem[];
  isRunning: boolean;
  streamingAssistantText?: string;
  showStreamingAssistantPlaceholder?: boolean;
}) {
  const visibleStreamingAssistantText = renderableStreamingAssistantText(
    streamingAssistantText,
    showStreamingAssistantPlaceholder
  );
  const hasStreamingAssistantText = visibleStreamingAssistantText.length > 0;
  return (
    <details className={cn("agent-run-root-activity", isRunning && "agent-run-root-activity-static")} open={isRunning}>
      <summary>
        <ChevronRight className="agent-tool-call-chevron" />
        <span className="agent-tool-call-group-label">
          {summarizeActivityTimeline(items, hasStreamingAssistantText ? 1 : 0)}
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
          return <ToolCallTimelineRow key={item.key} item={item} defaultOpen={false} />;
        })}
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
  streamingAssistantText = ""
}: {
  events: AgentRunEvent[];
  toolCalls?: AgentToolCall[];
  streamingAssistantText?: string;
}) {
  const items = useMemo(() => buildRunTimelineFromEvents(events, toolCalls), [events, toolCalls]);
  const hasStreamingAssistantText = streamingAssistantText.length > 0;
  const showStreamingAssistantPlaceholder = events.length > 0 && items.length === 0 && !hasStreamingAssistantText;

  if (items.length === 0 && !hasStreamingAssistantText && !showStreamingAssistantPlaceholder) {
    return null;
  }

  return (
    <ActivityTimeline
      items={items}
      isRunning={true}
      streamingAssistantText={streamingAssistantText}
      showStreamingAssistantPlaceholder={showStreamingAssistantPlaceholder}
    />
  );
}

export function AgentRunBlock({
  run,
  isMutating,
  onReviewRun,
  mode = "all",
  optimisticEvents = [],
  optimisticToolCalls = [],
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
  const hasStreamingAssistantText = streamingAssistantText.length > 0;
  const isRunning = run.status === "running";
  const showStreamingAssistantPlaceholder = isRunning && mergedEvents.length > 0 && activityTimeline.length === 0 && !hasStreamingAssistantText;
  const hasActivityContent =
    Boolean(run.error_text) ||
    activityTimeline.length > 0 ||
    hasStreamingAssistantText ||
    showStreamingAssistantPlaceholder;

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
              streamingAssistantText={streamingAssistantText}
              showStreamingAssistantPlaceholder={showStreamingAssistantPlaceholder}
            />
          ) : null}
        </>
      ) : null}

      {hasSummaryChanges ? (
        <div className="agent-run-changes-summary">
          <h4>{pendingCount > 0 ? `${pendingCount} proposed changes pending review` : "No pending changes in this run"}</h4>
          <Button type="button" size="sm" onClick={() => onReviewRun(run.id)} disabled={isMutating}>
            {pendingCount > 0 ? "Click to review proposed changes" : "View reviewed changes"}
          </Button>
          <div className="agent-run-change-chips">
            <span className="agent-run-change-chip">Entry x{typeSummary.entryCount}</span>
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

import { useMemo } from "react";
import { ChevronRight } from "lucide-react";

import type { AgentRun } from "../../lib/types";
import { cn } from "../../lib/utils";
import {
  buildRunActivityTimeline,
  reasoningSourceLabel,
  reasoningUpdatePreview,
  summarizeActivityTimeline,
  summarizeRunChangeTypes,
  type PendingAssistantActivityItem,
  type ReasoningUpdateSource,
  type RunToolCall
} from "./activity";
import { Button } from "../ui/button";
import { MarkdownRenderer } from "../ui/MarkdownRenderer";

interface AgentRunBlockProps {
  run: AgentRun;
  isMutating: boolean;
  onReviewRun: (runId: string) => void;
  mode?: "activity" | "summary" | "all";
}

function prettyDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function ToolCallDetailList({ toolCalls }: { toolCalls: RunToolCall[] }) {
  return (
    <ul className="agent-tool-call-list">
      {toolCalls.map((toolCall) => (
        <li key={toolCall.id}>
          <details className="agent-tool-call">
            <summary>
              <ChevronRight className="agent-tool-call-chevron" />
              <span className="agent-tool-call-name">{toolCall.tool_name}</span>
              <span className="agent-tool-call-status">{toolCall.status}</span>
              <span className="agent-tool-call-time muted">{prettyDateTime(toolCall.created_at)}</span>
            </summary>
            <div className="agent-tool-call-details">
              <p className="agent-tool-call-details-label">Arguments</p>
              <pre>{JSON.stringify(toolCall.input_json, null, 2)}</pre>
              <p className="agent-tool-call-details-label">Model-visible tool result</p>
              <pre>{toolCall.output_text || "(empty)"}</pre>
              <details>
                <summary className="agent-tool-call-details-label">Structured output (debug)</summary>
                <pre>{JSON.stringify(toolCall.output_json, null, 2)}</pre>
              </details>
            </div>
          </details>
        </li>
      ))}
    </ul>
  );
}

function ToolCallBatchGroup({
  toolCalls,
  isRunning
}: {
  toolCalls: RunToolCall[];
  isRunning: boolean;
}) {
  if (isRunning) {
    return (
      <div className="agent-tool-call-group agent-tool-call-group-static">
        <div className="agent-tool-call-group-summary">
          <span className="agent-tool-call-group-label">
            {toolCalls.length} tool call{toolCalls.length === 1 ? "" : "s"}
          </span>
          <span className="agent-tool-call-status">live</span>
        </div>
        <ToolCallDetailList toolCalls={toolCalls} />
      </div>
    );
  }

  return (
    <details className="agent-tool-call-group">
      <summary>
        <ChevronRight className="agent-tool-call-chevron" />
        <span className="agent-tool-call-group-label">
          {toolCalls.length} tool call{toolCalls.length === 1 ? "" : "s"}
        </span>
      </summary>
      <ToolCallDetailList toolCalls={toolCalls} />
    </details>
  );
}

function CollapsibleReasoningUpdate({ message, source, defaultOpen }: { message: string; source: ReasoningUpdateSource; defaultOpen?: boolean }) {
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

export function PendingAssistantActivityBlock({ activity }: { activity: PendingAssistantActivityItem[] }) {
  if (activity.length === 0) {
    return null;
  }
  const toolCount = activity.reduce((sum, item) => sum + (item.type === "tool_batch" ? item.toolNames.length : 0), 0);
  const updateCount = activity.filter((item) => item.type === "reasoning_update").length;
  const summaryParts: string[] = [];
  if (toolCount > 0) {
    summaryParts.push(`${toolCount} tool call${toolCount === 1 ? "" : "s"}`);
  }
  if (updateCount > 0) {
    summaryParts.push(`${updateCount} update${updateCount === 1 ? "" : "s"}`);
  }
  const summaryLabel = summaryParts.join(", ") || "Working…";

  return (
    <details className="agent-run-root-activity agent-run-root-activity-static" open>
      <summary>
        <ChevronRight className="agent-tool-call-chevron" />
        <span className="agent-tool-call-group-label">{summaryLabel}</span>
        <span className="agent-tool-call-status">live</span>
      </summary>
      <div className="agent-run-activity-timeline">
        {activity.map((item, index) => {
          const isLast = index === activity.length - 1;
          if (item.type === "reasoning_update") {
            return (
              <CollapsibleReasoningUpdate key={item.key} message={item.message} source={item.source} defaultOpen={isLast} />
            );
          }
          return (
            <details key={item.key} className="agent-tool-call-group agent-tool-call-group-static" open>
              <summary>
                <ChevronRight className="agent-tool-call-chevron" />
                <span className="agent-tool-call-group-label">
                  {item.toolNames.length} tool call{item.toolNames.length === 1 ? "" : "s"}
                </span>
              </summary>
              <ul className="agent-tool-call-list">
                {item.toolNames.map((toolName, toolIndex) => (
                  <li key={`${item.key}-${toolName}-${toolIndex}`}>
                    <details className="agent-tool-call agent-tool-call-static" open>
                      <summary>
                        <ChevronRight className="agent-tool-call-chevron" />
                        <span className="agent-tool-call-name">{toolName}</span>
                        <span className="agent-tool-call-status">streaming</span>
                      </summary>
                      <div className="agent-tool-call-details">
                        <p className="agent-tool-call-details-label">Details</p>
                        <p className="muted agent-tool-call-pending-detail">Waiting for full tool payload...</p>
                      </div>
                    </details>
                  </li>
                ))}
              </ul>
            </details>
          );
        })}
      </div>
    </details>
  );
}

export function AgentRunBlock({ run, isMutating, onReviewRun, mode = "all" }: AgentRunBlockProps) {
  const showActivity = mode !== "summary";
  const showSummary = mode !== "activity";
  const hasSummaryChanges = showSummary && run.change_items.length > 0;
  const hasActivityContent = Boolean(run.error_text) || run.tool_calls.length > 0;
  const pendingCount = run.change_items.filter((item) => item.status === "PENDING_REVIEW").length;
  const failedCount = run.change_items.filter((item) => item.status === "APPLY_FAILED").length;
  const typeSummary = summarizeRunChangeTypes(run.change_items);
  const activityTimeline = useMemo(() => buildRunActivityTimeline(run.tool_calls), [run.tool_calls]);
  const activitySummaryLabel = useMemo(() => summarizeActivityTimeline(activityTimeline), [activityTimeline]);
  const isRunning = run.status === "running";

  if (!hasActivityContent && !hasSummaryChanges) {
    return null;
  }

  return (
    <div className={cn("agent-run-block", showSummary && "agent-run-block-summary")}>
      {showActivity ? (
        <>
          {run.error_text ? <p className="error">{run.error_text}</p> : null}

          {run.tool_calls.length > 0 ? (
            <details className={cn("agent-run-root-activity", isRunning && "agent-run-root-activity-static")} open={isRunning}>
              <summary>
                <ChevronRight className="agent-tool-call-chevron" />
                <span className="agent-tool-call-group-label">{activitySummaryLabel}</span>
                {isRunning ? <span className="agent-tool-call-status">live</span> : null}
              </summary>
              <div className="agent-run-activity-timeline">
                {activityTimeline.map((item) => {
                  if (item.type === "reasoning_update") {
                    return (
                      <CollapsibleReasoningUpdate key={item.key} message={item.message} source={item.source} />
                    );
                  }
                  return (
                    <ToolCallBatchGroup key={item.key} toolCalls={item.toolCalls} isRunning={isRunning} />
                  );
                })}
              </div>
            </details>
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

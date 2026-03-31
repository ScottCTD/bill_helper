/**
 * CALLING SPEC:
 * - Purpose: render flat agent run activity rows (reasoning/assistant text as plain markdown; tool calls expandable).
 * - Inputs: callers that import `frontend/src/features/agent/AgentRunActivity.tsx`.
 * - Outputs: `AgentRunActivityRows`, `PendingAssistantActivityBlock`.
 * - Side effects: React rendering and tool hydration requests.
 */
import { useEffect, useMemo, useState } from "react";

import type { AgentRunEvent, AgentToolCall } from "../../lib/types";
import { cn } from "../../lib/utils";
import {
  buildRunTimelineFromEvents,
  isToolLifecycleTerminal,
  toolLifecycleLabel,
  toolLifecycleStatusClass,
  type RunActivityItem
} from "./activity";
import { MarkdownRenderer } from "../../components/ui/MarkdownRenderer";

const STREAMING_REASONING_PLACEHOLDER = "\u258d";

function prettyDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function renderableStreamingReasoningText(value: string, showPlaceholder: boolean): string {
  if (value.length > 0) {
    return value.trim().length > 0 ? value : STREAMING_REASONING_PLACEHOLDER;
  }
  return showPlaceholder ? STREAMING_REASONING_PLACEHOLDER : "";
}

/** Interleaved reasoning/assistant prose: `text-xs` / medium / foreground (tool rows use muted labels). */
function InterleavedAssistantMarkdown({ message }: { message: string }) {
  if (message === STREAMING_REASONING_PLACEHOLDER) {
    return (
      <p className="agent-run-interleaved-placeholder m-0">
        <span className="agent-message-caret">{STREAMING_REASONING_PLACEHOLDER}</span>
      </p>
    );
  }
  return <MarkdownRenderer markdown={message} className="agent-run-interleaved-markdown" />;
}

function ToolCallTimelineRow({
  item,
  defaultOpen,
  onInspectActivity,
  onHydrateToolCall,
  isHydrating = false
}: {
  item: Extract<RunActivityItem, { type: "tool_call" }>;
  defaultOpen?: boolean;
  onInspectActivity?: () => void;
  onHydrateToolCall?: (runId: string, toolCallId: string) => void;
  isHydrating?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(Boolean(defaultOpen));
  const toolCall = item.toolCall;
  const lifecycleStatusClass = toolLifecycleStatusClass(item.lifecycleEventType);
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
      <summary onClick={onInspectActivity}>
        <span className="agent-tool-call-name">{toolCall?.display_label ?? toolCall?.tool_name ?? "Tool call"}</span>
        <span
          className={cn("agent-tool-call-status-dot", lifecycleStatusClass)}
          title={toolLifecycleLabel(item.lifecycleEventType)}
        />
        <span className="agent-tool-call-time muted">{prettyDateTime(item.createdAt)}</span>
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

export function AgentRunActivityRows({
  items,
  onInspectActivity,
  onHydrateToolCall,
  hydratingToolCallIds,
  streamingReasoningText = "",
  showStreamingPlaceholder = false
}: {
  items: RunActivityItem[];
  onInspectActivity?: () => void;
  onHydrateToolCall?: (runId: string, toolCallId: string) => void;
  hydratingToolCallIds?: ReadonlySet<string>;
  streamingReasoningText?: string;
  showStreamingPlaceholder?: boolean;
}) {
  const visibleStreamingReasoningText = renderableStreamingReasoningText(streamingReasoningText, false);
  const hasStreamingReasoningText = visibleStreamingReasoningText.length > 0;
  return (
    <div className="agent-run-activity-timeline">
      {items.map((item) => {
        if (item.type === "reasoning_update") {
          return <InterleavedAssistantMarkdown key={item.key} message={item.message} />;
        }
        return (
          <ToolCallTimelineRow
            key={item.key}
            item={item}
            defaultOpen={false}
            onInspectActivity={onInspectActivity}
            onHydrateToolCall={onHydrateToolCall}
            isHydrating={Boolean(hydratingToolCallIds?.has(item.toolCallId))}
          />
        );
      })}
      {hasStreamingReasoningText ? (
        <InterleavedAssistantMarkdown message={visibleStreamingReasoningText} />
      ) : null}
      {showStreamingPlaceholder ? (
        <InterleavedAssistantMarkdown message={STREAMING_REASONING_PLACEHOLDER} />
      ) : null}
    </div>
  );
}

export function PendingAssistantActivityBlock({
  events,
  toolCalls = [],
  onInspectActivity,
  onHydrateToolCall,
  hydratingToolCallIds,
  streamingReasoningText = ""
}: {
  events: AgentRunEvent[];
  toolCalls?: AgentToolCall[];
  onInspectActivity?: () => void;
  onHydrateToolCall?: (runId: string, toolCallId: string) => void;
  hydratingToolCallIds?: ReadonlySet<string>;
  streamingReasoningText?: string;
}) {
  const items = useMemo(() => buildRunTimelineFromEvents(events, toolCalls), [events, toolCalls]);
  const hasStreamingReasoningText = streamingReasoningText.length > 0;
  const showStreamingPlaceholder =
    events.length > 0 && items.length === 0 && !hasStreamingReasoningText;

  if (items.length === 0 && !hasStreamingReasoningText && !showStreamingPlaceholder) {
    return null;
  }

  return (
    <AgentRunActivityRows
      items={items}
      onInspectActivity={onInspectActivity}
      onHydrateToolCall={onHydrateToolCall}
      hydratingToolCallIds={hydratingToolCallIds}
      streamingReasoningText={streamingReasoningText}
      showStreamingPlaceholder={showStreamingPlaceholder}
    />
  );
}

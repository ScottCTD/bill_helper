/**
 * CALLING SPEC:
 * - Purpose: provide the `activity` frontend module.
 * - Inputs: callers that import `frontend/src/features/agent/activity.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `activity`.
 * - Side effects: module-local frontend behavior only.
 */
import type {
  AgentChangeItem,
  AgentRun,
  AgentRunEvent,
  AgentRunEventSource,
  AgentRunEventType,
  AgentThreadDetail
} from "../../lib/types";

export type RunToolCall = AgentRun["tool_calls"][number];
export type ReasoningUpdateSource = AgentRunEventSource;

type ToolLifecycleEventType =
  | "tool_call_queued"
  | "tool_call_started"
  | "tool_call_completed"
  | "tool_call_failed"
  | "tool_call_cancelled";

interface RunActivityToolCallItem {
  type: "tool_call";
  key: string;
  runId: string;
  toolCallId: string;
  toolCall: RunToolCall | null;
  lifecycleEventType: ToolLifecycleEventType;
  createdAt: string;
}

interface RunActivityReasoningUpdate {
  type: "reasoning_update";
  key: string;
  message: string;
  source: ReasoningUpdateSource;
  createdAt: string;
}

export type RunActivityItem = RunActivityToolCallItem | RunActivityReasoningUpdate;

function byTimestamp(left: string, right: string): number {
  return new Date(left).getTime() - new Date(right).getTime();
}

function sortedToolCalls(toolCalls: RunToolCall[]): RunToolCall[] {
  return [...toolCalls].sort((left, right) => byTimestamp(left.created_at, right.created_at));
}

export function sortRunsByCreatedAt(runs: AgentRun[]): AgentRun[] {
  return [...runs].sort((left, right) => byTimestamp(left.created_at, right.created_at));
}

export function runsByAssistantMessage(detail: AgentThreadDetail | undefined): Map<string, AgentRun[]> {
  const map = new Map<string, AgentRun[]>();
  sortRunsByCreatedAt(detail?.runs ?? []).forEach((run) => {
    if (!run.assistant_message_id) {
      return;
    }
    const runs = map.get(run.assistant_message_id);
    if (runs) {
      runs.push(run);
      return;
    }
    map.set(run.assistant_message_id, [run]);
  });
  return map;
}

export function runsWithoutAssistantMessage(detail: AgentThreadDetail | undefined): AgentRun[] {
  return sortRunsByCreatedAt((detail?.runs ?? []).filter((run) => !run.assistant_message_id));
}

export function runsWithoutAssistantMessageByUserMessage(detail: AgentThreadDetail | undefined): Map<string, AgentRun[]> {
  const map = new Map<string, AgentRun[]>();
  runsWithoutAssistantMessage(detail).forEach((run) => {
    const runs = map.get(run.user_message_id);
    if (runs) {
      runs.push(run);
      return;
    }
    map.set(run.user_message_id, [run]);
  });
  return map;
}

export function totalRunMetric(
  runs: AgentRun[],
  field: "input_tokens" | "output_tokens" | "cache_read_tokens" | "cache_write_tokens" | "total_cost_usd"
): number | null {
  let total = 0;
  let hasValue = false;
  runs.forEach((run) => {
    const value = run[field];
    if (typeof value === "number") {
      total += value;
      hasValue = true;
    }
  });
  return hasValue ? total : null;
}

export function latestRunMetric(
  runs: AgentRun[],
  field: "input_tokens" | "output_tokens" | "cache_read_tokens" | "cache_write_tokens" | "total_cost_usd"
): number | null {
  const sorted = sortRunsByCreatedAt(runs);
  for (let index = sorted.length - 1; index >= 0; index -= 1) {
    const value = sorted[index][field];
    if (typeof value === "number") {
      return value;
    }
  }
  return null;
}

export function buildThreadUsageTotals(detail: AgentThreadDetail | undefined): {
  context: number | null;
  input: number | null;
  output: number | null;
  cacheRead: number | null;
  totalCost: number | null;
} {
  const runs = detail?.runs ?? [];
  return {
    context: detail?.current_context_tokens ?? null,
    input: totalRunMetric(runs, "input_tokens"),
    output: totalRunMetric(runs, "output_tokens"),
    cacheRead: totalRunMetric(runs, "cache_read_tokens"),
    totalCost: totalRunMetric(runs, "total_cost_usd")
  };
}

export function summarizeRunChangeTypes(changeItems: AgentChangeItem[]): {
  entryCount: number;
  tagCount: number;
  entityCount: number;
  groupCount: number;
} {
  let entryCount = 0;
  let tagCount = 0;
  let entityCount = 0;
  let groupCount = 0;

  changeItems.forEach((item) => {
    if (item.change_type.endsWith("_entry")) {
      entryCount += 1;
      return;
    }
    if (item.change_type.includes("group")) {
      groupCount += 1;
      return;
    }
    if (item.change_type.endsWith("_tag")) {
      tagCount += 1;
      return;
    }
    if (item.change_type.endsWith("_entity")) {
      entityCount += 1;
    }
  });

  return { entryCount, tagCount, entityCount, groupCount };
}

function sortRunEvents(events: AgentRunEvent[]): AgentRunEvent[] {
  return [...events].sort((left, right) => {
    if (left.sequence_index !== right.sequence_index) {
      return left.sequence_index - right.sequence_index;
    }
    return byTimestamp(left.created_at, right.created_at);
  });
}

export function mergeRunEvents(persisted: AgentRunEvent[], optimistic: AgentRunEvent[] = []): AgentRunEvent[] {
  const byId = new Map<string, AgentRunEvent>();
  [...persisted, ...optimistic].forEach((event) => {
    byId.set(event.id, event);
  });
  return sortRunEvents([...byId.values()]);
}

function mergeToolCallSnapshot(current: RunToolCall, incoming: RunToolCall): RunToolCall {
  const shouldPreserveCurrentPayload = current.has_full_payload && !incoming.has_full_payload;

  return {
    ...current,
    ...incoming,
    input_json: shouldPreserveCurrentPayload ? current.input_json : incoming.input_json,
    output_json: shouldPreserveCurrentPayload ? current.output_json : incoming.output_json,
    output_text: shouldPreserveCurrentPayload ? current.output_text : incoming.output_text,
    has_full_payload: current.has_full_payload || incoming.has_full_payload
  };
}

export function mergeRunToolCalls(persisted: RunToolCall[], optimistic: RunToolCall[] = []): RunToolCall[] {
  const byId = new Map<string, RunToolCall>();
  [...persisted, ...optimistic].forEach((toolCall) => {
    const existing = byId.get(toolCall.id);
    byId.set(toolCall.id, existing ? mergeToolCallSnapshot(existing, toolCall) : toolCall);
  });
  return sortedToolCalls([...byId.values()]);
}

function isToolLifecycleEventType(value: AgentRunEventType): value is ToolLifecycleEventType {
  return (
    value === "tool_call_queued" ||
    value === "tool_call_started" ||
    value === "tool_call_completed" ||
    value === "tool_call_failed" ||
    value === "tool_call_cancelled"
  );
}

export function buildRunTimelineFromEvents(events: AgentRunEvent[], toolCalls: RunToolCall[]): RunActivityItem[] {
  const mergedEvents = sortRunEvents(events);
  const timeline: RunActivityItem[] = [];
  const mergedToolCalls = mergeRunToolCalls(toolCalls);
  const toolCallById = new Map(mergedToolCalls.map((toolCall) => [toolCall.id, toolCall]));
  const seenToolItems = new Map<string, RunActivityToolCallItem>();

  mergedEvents.forEach((event) => {
    if (event.event_type === "reasoning_update") {
      const normalized = (event.message || "").trim();
      if (!normalized) {
        return;
      }
      timeline.push({
        type: "reasoning_update",
        key: event.id,
        message: normalized,
        source: event.source ?? "tool_call",
        createdAt: event.created_at
      });
      return;
    }

    if (!isToolLifecycleEventType(event.event_type) || !event.tool_call_id) {
      return;
    }

    const existingItem = seenToolItems.get(event.tool_call_id);
    if (existingItem) {
      existingItem.toolCall = existingItem.toolCall ?? toolCallById.get(event.tool_call_id) ?? null;
      existingItem.lifecycleEventType = event.event_type;
      existingItem.createdAt = event.created_at;
      return;
    }

    const item: RunActivityToolCallItem = {
      type: "tool_call",
      key: event.tool_call_id,
      runId: event.run_id,
      toolCallId: event.tool_call_id,
      toolCall: toolCallById.get(event.tool_call_id) ?? null,
      lifecycleEventType: event.event_type,
      createdAt: event.created_at
    };
    seenToolItems.set(event.tool_call_id, item);
    timeline.push(item);
  });

  return timeline;
}

export function summarizeActivityTimeline(items: RunActivityItem[], extraUpdateCount: number = 0): string {
  const toolCount = items.filter((item) => item.type === "tool_call").length;
  const updateCount = items.filter((item) => item.type === "reasoning_update").length + extraUpdateCount;
  const parts: string[] = [];
  if (toolCount > 0) {
    parts.push(`${toolCount} tool call${toolCount === 1 ? "" : "s"}`);
  }
  if (updateCount > 0) {
    parts.push(`${updateCount} update${updateCount === 1 ? "" : "s"}`);
  }
  return parts.join(", ") || "Activity";
}

function firstLinePreview(text: string, maxLength: number = 80): string {
  const firstLine = text.split("\n")[0].replace(/^#+\s*/, "").trim();
  if (firstLine.length <= maxLength) {
    return firstLine;
  }
  return `${firstLine.slice(0, maxLength)}…`;
}

export function reasoningUpdatePreview(message: string): string {
  return firstLinePreview(message);
}

export function reasoningSourceLabel(source: ReasoningUpdateSource): string {
  switch (source) {
    case "model_reasoning":
      return "Reasoning";
    case "assistant_content":
      return "Assistant";
    case "tool_call":
      return "Update";
  }
}

export function toolLifecycleLabel(eventType: ToolLifecycleEventType): string {
  switch (eventType) {
    case "tool_call_queued":
      return "Queued";
    case "tool_call_started":
      return "Running";
    case "tool_call_completed":
      return "Completed";
    case "tool_call_failed":
      return "Failed";
    case "tool_call_cancelled":
      return "Cancelled";
  }
}

export function toolLifecycleStatusClass(eventType: ToolLifecycleEventType): string {
  switch (eventType) {
    case "tool_call_queued":
      return "is-queued";
    case "tool_call_started":
      return "is-running";
    case "tool_call_completed":
      return "is-completed";
    case "tool_call_failed":
      return "is-failed";
    case "tool_call_cancelled":
      return "is-cancelled";
  }
}

export function isToolLifecycleTerminal(eventType: ToolLifecycleEventType): boolean {
  return (
    eventType === "tool_call_completed" ||
    eventType === "tool_call_failed" ||
    eventType === "tool_call_cancelled"
  );
}

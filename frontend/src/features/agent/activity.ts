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
  source: AgentRunEventSource;
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

export function countActivityMetrics(items: RunActivityItem[]): { toolCount: number; updateCount: number } {
  return {
    toolCount: items.filter((item) => item.type === "tool_call").length,
    updateCount: items.filter((item) => item.type === "reasoning_update").length
  };
}

/** Wall-clock span from earliest run start to latest run end (uses completed_at when set, else created_at). */
export function aggregateWorkDurationMs(runs: AgentRun[]): number | null {
  if (runs.length === 0) {
    return null;
  }
  let minStart = Number.POSITIVE_INFINITY;
  let maxEnd = Number.NEGATIVE_INFINITY;
  runs.forEach((run) => {
    const start = new Date(run.created_at).getTime();
    if (!Number.isNaN(start)) {
      minStart = Math.min(minStart, start);
    }
    const endRaw = run.completed_at ?? run.created_at;
    const end = new Date(endRaw).getTime();
    if (!Number.isNaN(end)) {
      maxEnd = Math.max(maxEnd, end);
    }
  });
  if (!Number.isFinite(minStart) || !Number.isFinite(maxEnd) || maxEnd < minStart) {
    return null;
  }
  return maxEnd - minStart;
}

export function formatWorkedDurationLabel(durationMs: number): string {
  const minutes = Math.floor(durationMs / 60_000);
  if (minutes >= 1) {
    return `${minutes} minute${minutes === 1 ? "" : "s"}`;
  }
  const seconds = Math.max(1, Math.ceil(durationMs / 1000));
  return `${seconds} second${seconds === 1 ? "" : "s"}`;
}

export function buildAgentWorkSeparatorLabel(runs: AgentRun[], items: RunActivityItem[]): string {
  const durationMs = aggregateWorkDurationMs(runs);
  const { toolCount, updateCount } = countActivityMetrics(items);
  const parts: string[] = [];
  if (durationMs !== null && durationMs >= 0) {
    parts.push(`Worked for ${formatWorkedDurationLabel(durationMs)}`);
  }
  if (toolCount > 0) {
    parts.push(`${toolCount} tool call${toolCount === 1 ? "" : "s"}`);
  }
  if (updateCount > 0) {
    parts.push(`${updateCount} update${updateCount === 1 ? "" : "s"}`);
  }
  return parts.join(", ") || "Agent activity";
}

export function mergeRunActivityItems(
  runs: AgentRun[],
  getOptimistic: (runId: string) => { events: AgentRunEvent[]; toolCalls: RunToolCall[] }
): RunActivityItem[] {
  const merged: RunActivityItem[] = [];
  sortRunsByCreatedAt(runs).forEach((run) => {
    const { events: optEvents, toolCalls: optToolCalls } = getOptimistic(run.id);
    const mergedEvents = mergeRunEvents(run.events, optEvents);
    const mergedToolCalls = mergeRunToolCalls(run.tool_calls, optToolCalls);
    const items = buildRunTimelineFromEvents(mergedEvents, mergedToolCalls);
    items.forEach((item) => {
      merged.push({
        ...item,
        key: `${run.id}:${item.key}`
      });
    });
  });
  merged.sort((left, right) => byTimestamp(left.createdAt, right.createdAt));
  return merged;
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

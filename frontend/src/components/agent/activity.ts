import type { AgentChangeItem, AgentRun, AgentThreadDetail } from "../../lib/types";

const INTERMEDIATE_UPDATE_TOOL_NAME = "send_intermediate_update";

export type RunToolCall = AgentRun["tool_calls"][number];

interface RunActivityToolBatch {
  type: "tool_batch";
  key: string;
  toolCalls: RunToolCall[];
}

export type ReasoningUpdateSource = "model_reasoning" | "assistant_content" | "tool_call";

interface RunActivityReasoningUpdate {
  type: "reasoning_update";
  key: string;
  message: string;
  source: ReasoningUpdateSource;
  createdAt: string;
}

export type RunActivityItem = RunActivityToolBatch | RunActivityReasoningUpdate;

interface PendingAssistantToolBatchActivity {
  type: "tool_batch";
  key: string;
  toolNames: string[];
}

interface PendingAssistantReasoningUpdateActivity {
  type: "reasoning_update";
  key: string;
  message: string;
  source: ReasoningUpdateSource;
}

export type PendingAssistantActivityItem = PendingAssistantToolBatchActivity | PendingAssistantReasoningUpdateActivity;

export function sortRunsByCreatedAt(runs: AgentRun[]): AgentRun[] {
  return [...runs].sort((left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime());
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
    totalCost: totalRunMetric(runs, "total_cost_usd"),
  };
}

export function summarizeRunChangeTypes(changeItems: AgentChangeItem[]): {
  entryCount: number;
  tagCount: number;
  entityCount: number;
} {
  let entryCount = 0;
  let tagCount = 0;
  let entityCount = 0;

  changeItems.forEach((item) => {
    if (item.change_type.endsWith("_entry")) {
      entryCount += 1;
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

  return {
    entryCount,
    tagCount,
    entityCount
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function extractIntermediateUpdateFromToolCall(toolCall: RunToolCall): { message: string; source: ReasoningUpdateSource } | null {
  if (toolCall.tool_name !== INTERMEDIATE_UPDATE_TOOL_NAME) {
    return null;
  }
  const outputJson = asRecord(toolCall.output_json);
  const inputJson = asRecord(toolCall.input_json);

  let message: string | null = null;
  const outputMessage = outputJson?.message;
  if (typeof outputMessage === "string" && outputMessage.trim()) {
    message = outputMessage.trim();
  }
  if (!message) {
    const inputMessage = inputJson?.message;
    if (typeof inputMessage === "string" && inputMessage.trim()) {
      message = inputMessage.trim();
    }
  }
  if (!message) {
    return null;
  }

  const rawSource = (outputJson?.source ?? inputJson?.source) as string | undefined;
  const source: ReasoningUpdateSource =
    rawSource === "model_reasoning" || rawSource === "assistant_content" || rawSource === "tool_call"
      ? rawSource
      : "tool_call";

  return { message, source };
}

function sortToolCallsByCreatedAt(toolCalls: RunToolCall[]): RunToolCall[] {
  return [...toolCalls].sort((left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime());
}

export function buildRunActivityTimeline(toolCalls: RunToolCall[]): RunActivityItem[] {
  const timeline: RunActivityItem[] = [];
  const sortedCalls = sortToolCallsByCreatedAt(toolCalls);
  let pendingBatch: RunToolCall[] = [];

  const flushPendingBatch = () => {
    if (pendingBatch.length === 0) {
      return;
    }
    const first = pendingBatch[0];
    const last = pendingBatch[pendingBatch.length - 1];
    timeline.push({
      type: "tool_batch",
      key: `${first.id}-${last.id}`,
      toolCalls: pendingBatch
    });
    pendingBatch = [];
  };

  sortedCalls.forEach((toolCall) => {
    const update = extractIntermediateUpdateFromToolCall(toolCall);
    if (!update) {
      pendingBatch.push(toolCall);
      return;
    }
    flushPendingBatch();
    timeline.push({
      type: "reasoning_update",
      key: toolCall.id,
      message: update.message,
      source: update.source,
      createdAt: toolCall.created_at
    });
  });
  flushPendingBatch();
  return timeline;
}

export function appendPendingToolCallToActivity(
  activity: PendingAssistantActivityItem[],
  toolName: string
): PendingAssistantActivityItem[] {
  if (!toolName || toolName === INTERMEDIATE_UPDATE_TOOL_NAME) {
    return activity;
  }

  const last = activity[activity.length - 1];
  if (last?.type === "tool_batch") {
    const updatedBatch: PendingAssistantToolBatchActivity = {
      ...last,
      toolNames: [...last.toolNames, toolName]
    };
    return [...activity.slice(0, -1), updatedBatch];
  }
  return [
    ...activity,
    {
      type: "tool_batch",
      key: `tool-batch-${activity.length + 1}-${Date.now()}`,
      toolNames: [toolName]
    }
  ];
}

export function appendPendingReasoningUpdateToActivity(
  activity: PendingAssistantActivityItem[],
  message: string,
  source: ReasoningUpdateSource = "tool_call"
): PendingAssistantActivityItem[] {
  const normalized = message.trim();
  if (!normalized) {
    return activity;
  }
  return [
    ...activity,
    {
      type: "reasoning_update",
      key: `reasoning-update-${activity.length + 1}-${Date.now()}`,
      message: normalized,
      source
    }
  ];
}

export function summarizeActivityTimeline(items: RunActivityItem[]): string {
  let toolCount = 0;
  let updateCount = 0;
  items.forEach((item) => {
    if (item.type === "tool_batch") {
      toolCount += item.toolCalls.length;
    } else {
      updateCount += 1;
    }
  });
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

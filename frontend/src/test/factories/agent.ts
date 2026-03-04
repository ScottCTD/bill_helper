import type { AgentChangeItem, AgentRun, AgentToolCall } from "../../lib/types";

export function buildToolCall(overrides: Partial<AgentToolCall> = {}): AgentToolCall {
  return {
    id: overrides.id ?? "tool-call-1",
    run_id: overrides.run_id ?? "run-1",
    tool_name: overrides.tool_name ?? "list_entries",
    input_json: overrides.input_json ?? {},
    output_json: overrides.output_json ?? {},
    output_text: overrides.output_text ?? "OK\nsummary: test",
    status: overrides.status ?? "ok",
    created_at: overrides.created_at ?? "2026-02-15T10:00:00Z"
  };
}

export function buildChangeItem(overrides: Partial<AgentChangeItem> = {}): AgentChangeItem {
  return {
    id: overrides.id ?? "change-item-1",
    run_id: overrides.run_id ?? "run-1",
    change_type: overrides.change_type ?? "create_entry",
    payload_json: overrides.payload_json ?? { name: "test" },
    rationale_text: overrides.rationale_text ?? "rationale",
    status: overrides.status ?? "PENDING_REVIEW",
    review_note: overrides.review_note ?? null,
    applied_resource_type: overrides.applied_resource_type ?? null,
    applied_resource_id: overrides.applied_resource_id ?? null,
    created_at: overrides.created_at ?? "2026-02-15T10:00:00Z",
    updated_at: overrides.updated_at ?? "2026-02-15T10:00:00Z",
    review_actions: overrides.review_actions ?? []
  };
}

export function buildRun(overrides: Partial<AgentRun> = {}): AgentRun {
  return {
    id: overrides.id ?? "run-1",
    thread_id: overrides.thread_id ?? "thread-1",
    user_message_id: overrides.user_message_id ?? "message-user-1",
    assistant_message_id: overrides.assistant_message_id !== undefined ? overrides.assistant_message_id : "message-assistant-1",
    status: overrides.status ?? "completed",
    model_name: overrides.model_name ?? "gpt-test",
    context_tokens: overrides.context_tokens !== undefined ? overrides.context_tokens : 10,
    input_tokens: overrides.input_tokens !== undefined ? overrides.input_tokens : 10,
    output_tokens: overrides.output_tokens !== undefined ? overrides.output_tokens : 20,
    cache_read_tokens: overrides.cache_read_tokens !== undefined ? overrides.cache_read_tokens : 0,
    cache_write_tokens: overrides.cache_write_tokens !== undefined ? overrides.cache_write_tokens : 0,
    input_cost_usd: overrides.input_cost_usd !== undefined ? overrides.input_cost_usd : 0.001,
    output_cost_usd: overrides.output_cost_usd !== undefined ? overrides.output_cost_usd : 0.002,
    total_cost_usd: overrides.total_cost_usd !== undefined ? overrides.total_cost_usd : 0.003,
    error_text: overrides.error_text !== undefined ? overrides.error_text : null,
    created_at: overrides.created_at ?? "2026-02-15T10:00:00Z",
    completed_at: overrides.completed_at !== undefined ? overrides.completed_at : "2026-02-15T10:00:01Z",
    tool_calls: overrides.tool_calls ?? [],
    change_items: overrides.change_items ?? []
  };
}

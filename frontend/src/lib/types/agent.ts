/**
 * CALLING SPEC:
 * - Purpose: define agent-thread, review, and streaming contracts for the frontend.
 * - Inputs: frontend modules that render agent threads, runs, tool calls, and review workflows.
 * - Outputs: agent-domain interfaces and event unions.
 * - Side effects: type declarations only.
 */

export type AgentMessageRole = "user" | "assistant" | "system";
export type AgentRunStatus = "running" | "completed" | "failed";
export type AgentToolCallStatus = "queued" | "running" | "ok" | "error" | "cancelled";
export type AgentRunEventType =
  | "run_started"
  | "reasoning_update"
  | "tool_call_queued"
  | "tool_call_started"
  | "tool_call_completed"
  | "tool_call_failed"
  | "tool_call_cancelled"
  | "run_completed"
  | "run_failed";
export type AgentRunEventSource = "model_reasoning" | "assistant_content" | "tool_call";
export type AgentChangeType =
  | "create_entry"
  | "update_entry"
  | "delete_entry"
  | "create_account"
  | "update_account"
  | "delete_account"
  | "create_snapshot"
  | "delete_snapshot"
  | "create_group"
  | "update_group"
  | "delete_group"
  | "create_group_member"
  | "delete_group_member"
  | "create_tag"
  | "update_tag"
  | "delete_tag"
  | "create_entity"
  | "update_entity"
  | "delete_entity";
export type AgentChangeStatus = "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "APPLIED" | "APPLY_FAILED";
export type AgentReviewActionType = "approve" | "reject";

export interface AgentThread {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentThreadSummary extends AgentThread {
  last_message_preview: string | null;
  pending_change_count: number;
  has_running_run: boolean;
}

export interface AgentMessageAttachment {
  id: string;
  message_id: string;
  mime_type: string;
  file_path: string;
  attachment_url: string;
  created_at: string;
}

export interface AgentMessage {
  id: string;
  thread_id: string;
  role: AgentMessageRole;
  content_markdown: string;
  created_at: string;
  attachments: AgentMessageAttachment[];
}

export interface AgentToolCall {
  id: string;
  run_id: string;
  llm_tool_call_id: string | null;
  tool_name: string;
  input_json: Record<string, unknown> | null;
  output_json: Record<string, unknown> | null;
  output_text: string | null;
  has_full_payload: boolean;
  status: AgentToolCallStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface AgentRunEvent {
  id: string;
  run_id: string;
  sequence_index: number;
  event_type: AgentRunEventType;
  source: AgentRunEventSource | null;
  message: string | null;
  tool_call_id: string | null;
  created_at: string;
}

export interface AgentReviewAction {
  id: string;
  change_item_id: string;
  action: AgentReviewActionType;
  actor: string;
  note: string | null;
  created_at: string;
}

export interface AgentChangeItem {
  id: string;
  run_id: string;
  change_type: AgentChangeType;
  payload_json: Record<string, unknown>;
  rationale_text: string;
  status: AgentChangeStatus;
  review_note: string | null;
  applied_resource_type: string | null;
  applied_resource_id: string | null;
  created_at: string;
  updated_at: string;
  review_actions: AgentReviewAction[];
}

export interface AgentRun {
  id: string;
  thread_id: string;
  user_message_id: string;
  assistant_message_id: string | null;
  status: AgentRunStatus;
  model_name: string;
  context_tokens: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cache_read_tokens: number | null;
  cache_write_tokens: number | null;
  input_cost_usd: number | null;
  output_cost_usd: number | null;
  total_cost_usd: number | null;
  error_text: string | null;
  created_at: string;
  completed_at: string | null;
  events: AgentRunEvent[];
  tool_calls: AgentToolCall[];
  change_items: AgentChangeItem[];
}

export interface AgentThreadDetail {
  thread: AgentThread;
  messages: AgentMessage[];
  runs: AgentRun[];
  configured_model_name: string;
  current_context_tokens: number | null;
}

export type AgentStreamEvent =
  | {
      type: "reasoning_delta";
      run_id: string;
      delta: string;
    }
  | {
      type: "text_delta";
      run_id: string;
      delta: string;
    }
  | {
      type: "run_event";
      run_id: string;
      event: AgentRunEvent;
      tool_call?: AgentToolCall;
    };

export type EntryKind = "EXPENSE" | "INCOME" | "TRANSFER";
export type GroupType = "BUNDLE" | "SPLIT" | "RECURRING";
export type GroupMemberRole = "PARENT" | "CHILD";
export type GroupMemberTarget =
  | { target_type: "entry"; entry_id: string }
  | { target_type: "child_group"; group_id: string };

export interface GroupMemberCreatePayload {
  target: GroupMemberTarget;
  member_role?: GroupMemberRole;
}

export interface Tag {
  id: number;
  name: string;
  color: string | null;
  description?: string | null;
  type?: string | null;
  entry_count?: number | null;
}

export interface EntryTag {
  id: number;
  name: string;
  color: string | null;
  description?: string | null;
  type?: string | null;
}

export interface Entity {
  id: string;
  name: string;
  category: string | null;
  is_account: boolean;
  from_count?: number | null;
  to_count?: number | null;
  account_count?: number | null;
  entry_count?: number | null;
  net_amount_minor?: number | null;
  net_amount_currency_code?: string | null;
  net_amount_mixed_currencies?: boolean;
}

export interface User {
  id: string;
  name: string;
  is_admin: boolean;
  is_current_user: boolean;
  account_count?: number | null;
  entry_count?: number | null;
}

export interface Currency {
  code: string;
  name: string;
  entry_count: number;
  is_placeholder: boolean;
}

export interface Taxonomy {
  id: string;
  key: string;
  applies_to: string;
  cardinality: string;
  display_name: string;
}

export interface TaxonomyTerm {
  id: string;
  taxonomy_id: string;
  name: string;
  normalized_name: string;
  parent_term_id: string | null;
  description?: string | null;
  usage_count: number;
}

export interface Account {
  id: string;
  owner_user_id: string;
  name: string;
  markdown_body: string | null;
  currency_code: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Snapshot {
  id: string;
  account_id: string;
  snapshot_at: string;
  balance_minor: number;
  note: string | null;
  created_at: string;
}

export interface SnapshotSummary {
  id: string;
  snapshot_at: string;
  balance_minor: number;
  note: string | null;
}

export interface ReconciliationInterval {
  start_snapshot: SnapshotSummary;
  end_snapshot: SnapshotSummary | null;
  is_open: boolean;
  tracked_change_minor: number;
  bank_change_minor: number | null;
  delta_minor: number | null;
  entry_count: number;
}

export interface Reconciliation {
  account_id: string;
  account_name: string;
  currency_code: string;
  as_of: string;
  intervals: ReconciliationInterval[];
}

export interface DashboardReconciliation {
  account_id: string;
  account_name: string;
  currency_code: string;
  latest_snapshot_at: string | null;
  current_tracked_change_minor: number | null;
  last_closed_delta_minor: number | null;
  mismatched_interval_count: number;
  reconciled_interval_count: number;
}

export interface EntryGroupRef {
  id: string;
  name: string;
  group_type: GroupType;
}

export interface Entry {
  id: string;
  account_id: string | null;
  kind: EntryKind;
  occurred_at: string;
  name: string;
  amount_minor: number;
  currency_code: string;
  from_entity_id: string | null;
  to_entity_id: string | null;
  owner_user_id: string;
  from_entity: string | null;
  from_entity_missing: boolean;
  to_entity: string | null;
  to_entity_missing: boolean;
  owner: string | null;
  markdown_body: string | null;
  created_at: string;
  updated_at: string;
  tags: EntryTag[];
  direct_group: EntryGroupRef | null;
  direct_group_member_role: GroupMemberRole | null;
  group_path: EntryGroupRef[];
}

export interface EntryDetail extends Entry {}

export interface EntryListResponse {
  items: Entry[];
  total: number;
  limit: number;
  offset: number;
}

export interface EntryTagSuggestionRequest {
  entry_id?: string | null;
  kind: EntryKind;
  occurred_at: string;
  currency_code: string;
  amount_minor?: number | null;
  name?: string | null;
  from_entity_id?: string | null;
  from_entity?: string | null;
  to_entity_id?: string | null;
  to_entity?: string | null;
  owner_user_id?: string | null;
  markdown_body?: string | null;
  current_tags: string[];
}

export interface EntryTagSuggestionResponse {
  suggested_tags: string[];
}

export interface GroupNode {
  graph_id: string;
  membership_id: string;
  subject_id: string;
  node_type: "ENTRY" | "GROUP";
  name: string;
  member_role: GroupMemberRole | null;
  representative_occurred_at: string | null;
  kind: EntryKind | null;
  amount_minor: number | null;
  currency_code: string | null;
  occurred_at: string | null;
  group_type: GroupType | null;
  descendant_entry_count: number | null;
  first_occurred_at: string | null;
  last_occurred_at: string | null;
}

export interface GroupEdge {
  id: string;
  source_graph_id: string;
  target_graph_id: string;
  group_type: GroupType;
}

export interface GroupGraph {
  id: string;
  name: string;
  group_type: GroupType;
  parent_group_id: string | null;
  direct_member_count: number;
  direct_entry_count: number;
  direct_child_group_count: number;
  descendant_entry_count: number;
  first_occurred_at: string | null;
  last_occurred_at: string | null;
  nodes: GroupNode[];
  edges: GroupEdge[];
}

export interface GroupSummary {
  id: string;
  name: string;
  group_type: GroupType;
  parent_group_id: string | null;
  direct_member_count: number;
  direct_entry_count: number;
  direct_child_group_count: number;
  descendant_entry_count: number;
  first_occurred_at: string | null;
  last_occurred_at: string | null;
}

export interface DailyExpensePoint {
  date: string;
  currency_code: string;
  total_minor: number;
}

export interface TopTag {
  tag: string;
  currency_code: string;
  total_minor: number;
}

export type FilterRuleField = "entry_kind" | "tags" | "is_internal_transfer";
export type FilterRuleConditionOperator = "is" | "has_any" | "has_none";
export type FilterRuleLogicalOperator = "AND" | "OR";

export interface FilterRuleCondition {
  type: "condition";
  field: FilterRuleField;
  operator: FilterRuleConditionOperator;
  value: string | boolean | string[];
}

export interface FilterRuleGroup {
  type: "group";
  operator: FilterRuleLogicalOperator;
  children: FilterRuleNode[];
}

export type FilterRuleNode = FilterRuleCondition | FilterRuleGroup;

export interface FilterGroupRule {
  include: FilterRuleGroup;
  exclude: FilterRuleGroup | null;
}

export interface FilterGroup {
  id: string;
  key: string;
  name: string;
  description: string | null;
  color: string | null;
  is_default: boolean;
  position: number;
  rule: FilterGroupRule;
  rule_summary: string;
  created_at: string;
  updated_at: string;
}

export interface DashboardKpis {
  expense_total_minor: number;
  income_total_minor: number;
  net_total_minor: number;
  average_expense_day_minor: number;
  median_expense_day_minor: number;
  spending_days: number;
}

export interface DashboardFilterGroupSummary {
  filter_group_id: string;
  key: string;
  name: string;
  color: string | null;
  total_minor: number;
  share: number;
}

export interface DashboardDailySpendingPoint {
  date: string;
  expense_total_minor: number;
  filter_group_totals: Record<string, number>;
}

export interface DashboardMonthlyTrendPoint {
  month: string;
  expense_total_minor: number;
  income_total_minor: number;
  filter_group_totals: Record<string, number>;
}

export interface DashboardBreakdownItem {
  label: string;
  total_minor: number;
  share: number;
}

export interface DashboardWeekdaySpendingPoint {
  weekday: string;
  total_minor: number;
}

export interface DashboardLargestExpenseItem {
  id: string;
  occurred_at: string;
  name: string;
  to_entity: string | null;
  amount_minor: number;
  matching_filter_group_keys: string[];
}

export interface DashboardProjection {
  is_current_month: boolean;
  days_elapsed: number;
  days_remaining: number;
  spent_to_date_minor: number;
  projected_total_minor: number | null;
  projected_remaining_minor: number | null;
  projected_filter_group_totals: Record<string, number>;
}

export interface DashboardTimeline {
  months: string[];
}

export interface Dashboard {
  month: string;
  currency_code: string;
  kpis: DashboardKpis;
  filter_groups: DashboardFilterGroupSummary[];
  daily_spending: DashboardDailySpendingPoint[];
  monthly_trend: DashboardMonthlyTrendPoint[];
  spending_by_from: DashboardBreakdownItem[];
  spending_by_to: DashboardBreakdownItem[];
  spending_by_tag: DashboardBreakdownItem[];
  weekday_spending: DashboardWeekdaySpendingPoint[];
  largest_expenses: DashboardLargestExpenseItem[];
  projection: DashboardProjection;
  reconciliation: DashboardReconciliation[];
}

export interface RuntimeSettingsOverrides {
  user_memory: string[] | null;
  default_currency_code: string | null;
  dashboard_currency_code: string | null;
  agent_model: string | null;
  entry_tagging_model: string | null;
  available_agent_models: string[] | null;
  agent_max_steps: number | null;
  agent_bulk_max_concurrent_threads: number | null;
  agent_retry_max_attempts: number | null;
  agent_retry_initial_wait_seconds: number | null;
  agent_retry_max_wait_seconds: number | null;
  agent_retry_backoff_multiplier: number | null;
  agent_max_image_size_bytes: number | null;
  agent_max_images_per_message: number | null;
  agent_base_url: string | null;
  agent_api_key_configured: boolean;
}

export interface RuntimeSettings {
  user_memory: string[] | null;
  default_currency_code: string;
  dashboard_currency_code: string;
  agent_model: string;
  entry_tagging_model: string | null;
  available_agent_models: string[];
  agent_max_steps: number;
  agent_bulk_max_concurrent_threads: number;
  agent_retry_max_attempts: number;
  agent_retry_initial_wait_seconds: number;
  agent_retry_max_wait_seconds: number;
  agent_retry_backoff_multiplier: number;
  agent_max_image_size_bytes: number;
  agent_max_images_per_message: number;
  agent_base_url: string | null;
  agent_api_key_configured: boolean;
  overrides: RuntimeSettingsOverrides;
}

export interface RuntimeSettingsUpdatePayload {
  user_memory?: string[] | null;
  default_currency_code?: string | null;
  dashboard_currency_code?: string | null;
  agent_model?: string | null;
  entry_tagging_model?: string | null;
  available_agent_models?: string[] | null;
  agent_max_steps?: number | null;
  agent_bulk_max_concurrent_threads?: number | null;
  agent_retry_max_attempts?: number | null;
  agent_retry_initial_wait_seconds?: number | null;
  agent_retry_max_wait_seconds?: number | null;
  agent_retry_backoff_multiplier?: number | null;
  agent_max_image_size_bytes?: number | null;
  agent_max_images_per_message?: number | null;
  agent_base_url?: string | null;
  agent_api_key?: string | null;
}

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

export interface AuthUser {
  id: string;
  name: string;
  is_admin: boolean;
}

export interface AuthSession {
  user: AuthUser;
  session_id: string | null;
  is_admin_impersonation: boolean;
}

export interface AuthLoginResponse extends AuthSession {
  token: string;
}

export interface AdminSession {
  id: string;
  user_id: string;
  user_name: string;
  is_admin: boolean;
  is_admin_impersonation: boolean;
  created_at: string;
  expires_at: string | null;
  is_current: boolean;
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

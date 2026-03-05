import type {
  Account,
  AgentChangeItem,
  AgentRun,
  AgentStreamEvent,
  AgentThread,
  AgentThreadDetail,
  AgentThreadSummary,
  AgentToolCall,
  Currency,
  Dashboard,
  Entity,
  EntryDetail,
  EntryListResponse,
  GroupGraph,
  GroupSummary,
  Link,
  RuntimeSettings,
  Reconciliation,
  Snapshot,
  Taxonomy,
  TaxonomyTerm,
  Tag,
  User
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  const isFormData = init?.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers,
    ...init
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed (${response.status})`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function parseSseEventBlock(rawBlock: string): { eventType: string; data: string } | null {
  let eventType = "message";
  const dataLines: string[] = [];
  for (const line of rawBlock.split("\n")) {
    if (!line || line.startsWith(":")) {
      continue;
    }
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) {
    return null;
  }
  return { eventType, data: dataLines.join("\n") };
}

function readSseBlocks(buffer: string): { blocks: string[]; remainder: string } {
  const blocks: string[] = [];
  let cursor = 0;
  while (cursor < buffer.length) {
    const end = buffer.indexOf("\n\n", cursor);
    if (end < 0) {
      break;
    }
    blocks.push(buffer.slice(cursor, end));
    cursor = end + 2;
  }
  return { blocks, remainder: buffer.slice(cursor) };
}

function parseAgentStreamEvent(rawBlock: string): AgentStreamEvent | null {
  const parsedBlock = parseSseEventBlock(rawBlock);
  if (!parsedBlock) {
    return null;
  }
  if (!parsedBlock.eventType) {
    return null;
  }
  let payload: unknown;
  try {
    payload = JSON.parse(parsedBlock.data);
  } catch {
    return null;
  }
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const maybeType = (payload as { type?: unknown }).type;
  if (typeof maybeType !== "string") {
    return null;
  }
  return payload as AgentStreamEvent;
}

export function listAccounts(): Promise<Account[]> {
  return request<Account[]>("/api/v1/accounts");
}

export function listEntities(): Promise<Entity[]> {
  return request<Entity[]>("/api/v1/entities");
}

export function createEntity(payload: { name: string; category?: string | null }): Promise<Entity> {
  return request<Entity>("/api/v1/entities", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateEntity(entityId: string, payload: { name?: string; category?: string | null }): Promise<Entity> {
  return request<Entity>(`/api/v1/entities/${entityId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function listTags(): Promise<Tag[]> {
  return request<Tag[]>("/api/v1/tags");
}

export function listUsers(): Promise<User[]> {
  return request<User[]>("/api/v1/users");
}

export function createUser(payload: { name: string }): Promise<User> {
  return request<User>("/api/v1/users", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateUser(userId: string, payload: { name?: string }): Promise<User> {
  return request<User>(`/api/v1/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function createTag(payload: {
  name: string;
  color?: string | null;
  description?: string | null;
  type?: string | null;
}): Promise<Tag> {
  return request<Tag>("/api/v1/tags", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateTag(
  tagId: number,
  payload: { name?: string; color?: string | null; description?: string | null; type?: string | null }
): Promise<Tag> {
  return request<Tag>(`/api/v1/tags/${tagId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function listCurrencies(): Promise<Currency[]> {
  return request<Currency[]>("/api/v1/currencies");
}

export function listTaxonomies(): Promise<Taxonomy[]> {
  return request<Taxonomy[]>("/api/v1/taxonomies");
}

export function listTaxonomyTerms(taxonomyKey: string): Promise<TaxonomyTerm[]> {
  return request<TaxonomyTerm[]>(`/api/v1/taxonomies/${taxonomyKey}/terms`);
}

export function createTaxonomyTerm(
  taxonomyKey: string,
  payload: { name: string; parent_term_id?: string | null; description?: string | null }
): Promise<TaxonomyTerm> {
  return request<TaxonomyTerm>(`/api/v1/taxonomies/${taxonomyKey}/terms`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateTaxonomyTerm(
  taxonomyKey: string,
  termId: string,
  payload: { name?: string; description?: string | null }
): Promise<TaxonomyTerm> {
  return request<TaxonomyTerm>(`/api/v1/taxonomies/${taxonomyKey}/terms/${termId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function createAccount(payload: {
  owner_user_id?: string;
  name: string;
  markdown_body?: string | null;
  currency_code: string;
  is_active?: boolean;
}): Promise<Account> {
  return request<Account>("/api/v1/accounts", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateAccount(accountId: string, payload: Partial<Account>): Promise<Account> {
  return request<Account>(`/api/v1/accounts/${accountId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function createSnapshot(
  accountId: string,
  payload: { snapshot_at: string; balance_minor: number; note?: string }
): Promise<Snapshot> {
  return request<Snapshot>(`/api/v1/accounts/${accountId}/snapshots`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listSnapshots(accountId: string): Promise<Snapshot[]> {
  return request<Snapshot[]>(`/api/v1/accounts/${accountId}/snapshots`);
}

export function getReconciliation(accountId: string, asOf?: string): Promise<Reconciliation> {
  const params = new URLSearchParams();
  if (asOf) {
    params.set("as_of", asOf);
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<Reconciliation>(`/api/v1/accounts/${accountId}/reconciliation${suffix}`);
}

export function listEntries(params: {
  start_date?: string;
  end_date?: string;
  kind?: string;
  tag?: string;
  currency?: string;
  source?: string;
  account_id?: string;
  limit?: number;
  offset?: number;
}): Promise<EntryListResponse> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  return request<EntryListResponse>(`/api/v1/entries?${search.toString()}`);
}

export function createEntry(payload: {
  account_id?: string;
  kind: string;
  occurred_at: string;
  name: string;
  amount_minor: number;
  currency_code: string;
  from_entity_id?: string;
  to_entity_id?: string;
  owner_user_id?: string;
  from_entity?: string;
  to_entity?: string;
  owner?: string;
  markdown_body?: string;
  tags?: string[];
}) {
  return request("/api/v1/entries", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getEntry(entryId: string): Promise<EntryDetail> {
  return request<EntryDetail>(`/api/v1/entries/${entryId}`);
}

export function updateEntry(entryId: string, payload: object) {
  return request(`/api/v1/entries/${entryId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteEntry(entryId: string) {
  return request(`/api/v1/entries/${entryId}`, {
    method: "DELETE"
  });
}

export function createLink(entryId: string, payload: { target_entry_id: string; link_type: string; note?: string }): Promise<Link> {
  return request<Link>(`/api/v1/entries/${entryId}/links`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function deleteLink(linkId: string) {
  return request(`/api/v1/links/${linkId}`, {
    method: "DELETE"
  });
}

export function getGroup(groupId: string): Promise<GroupGraph> {
  return request<GroupGraph>(`/api/v1/groups/${groupId}`);
}

export function listGroups(): Promise<GroupSummary[]> {
  return request<GroupSummary[]>("/api/v1/groups");
}

export function getDashboard(month: string): Promise<Dashboard> {
  return request<Dashboard>(`/api/v1/dashboard?month=${month}`);
}

export function getRuntimeSettings(): Promise<RuntimeSettings> {
  return request<RuntimeSettings>("/api/v1/settings");
}

export function updateRuntimeSettings(payload: {
  current_user_name?: string | null;
  user_memory?: string | null;
  default_currency_code?: string | null;
  dashboard_currency_code?: string | null;
  agent_model?: string | null;
  agent_max_steps?: number | null;
  agent_retry_max_attempts?: number | null;
  agent_retry_initial_wait_seconds?: number | null;
  agent_retry_max_wait_seconds?: number | null;
  agent_retry_backoff_multiplier?: number | null;
  agent_max_image_size_bytes?: number | null;
  agent_max_images_per_message?: number | null;
  agent_base_url?: string | null;
  agent_api_key?: string | null;
}): Promise<RuntimeSettings> {
  return request<RuntimeSettings>("/api/v1/settings", {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function withApiBase(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export function listAgentThreads(): Promise<AgentThreadSummary[]> {
  return request<AgentThreadSummary[]>("/api/v1/agent/threads");
}

export function createAgentThread(payload?: { title?: string | null }): Promise<AgentThread> {
  return request<AgentThread>("/api/v1/agent/threads", {
    method: "POST",
    body: JSON.stringify(payload ?? {})
  });
}

export function getAgentThread(threadId: string): Promise<AgentThreadDetail> {
  return request<AgentThreadDetail>(`/api/v1/agent/threads/${threadId}`);
}

export function deleteAgentThread(threadId: string): Promise<void> {
  return request<void>(`/api/v1/agent/threads/${threadId}`, {
    method: "DELETE"
  });
}

export async function streamAgentMessage(payload: {
  threadId: string;
  content: string;
  files: File[];
  signal?: AbortSignal;
  onEvent: (event: AgentStreamEvent) => void;
}): Promise<void> {
  const formData = new FormData();
  formData.set("content", payload.content);
  payload.files.forEach((file) => {
    formData.append("files", file);
  });

  const response = await fetch(`${API_BASE_URL}/api/v1/agent/threads/${payload.threadId}/messages/stream`, {
    method: "POST",
    body: formData,
    signal: payload.signal,
    headers: {
      Accept: "text/event-stream"
    }
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed (${response.status})`);
  }
  if (!response.body) {
    throw new Error("Streaming response body is unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      break;
    }
    buffer += decoder.decode(value, { stream: true }).replace(/\r/g, "");
    const { blocks, remainder } = readSseBlocks(buffer);
    buffer = remainder;
    blocks.forEach((rawBlock) => {
      const event = parseAgentStreamEvent(rawBlock);
      if (event) {
        payload.onEvent(event);
      }
    });
  }
  if (buffer.trim()) {
    const event = parseAgentStreamEvent(buffer);
    if (event) {
      payload.onEvent(event);
    }
  }
}

export function getAgentRun(runId: string): Promise<AgentRun> {
  return request<AgentRun>(`/api/v1/agent/runs/${runId}`);
}

export function getAgentToolCall(toolCallId: string): Promise<AgentToolCall> {
  return request<AgentToolCall>(`/api/v1/agent/tool-calls/${toolCallId}`);
}

export function interruptAgentRun(runId: string): Promise<AgentRun> {
  return request<AgentRun>(`/api/v1/agent/runs/${runId}/interrupt`, {
    method: "POST"
  });
}

export function approveAgentChangeItem(payload: {
  itemId: string;
  note?: string;
  payload_override?: Record<string, unknown>;
}): Promise<AgentChangeItem> {
  return request<AgentChangeItem>(`/api/v1/agent/change-items/${payload.itemId}/approve`, {
    method: "POST",
    body: JSON.stringify({
      note: payload.note,
      payload_override: payload.payload_override
    })
  });
}

export function rejectAgentChangeItem(payload: { itemId: string; note?: string }): Promise<AgentChangeItem> {
  return request<AgentChangeItem>(`/api/v1/agent/change-items/${payload.itemId}/reject`, {
    method: "POST",
    body: JSON.stringify({
      note: payload.note
    })
  });
}

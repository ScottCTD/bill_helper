/**
 * CALLING SPEC:
 * - Purpose: expose agent thread, run, tool-call, and review API calls for the frontend.
 * - Inputs: thread ids, run ids, review payloads, stream callbacks, and optional file attachments.
 * - Outputs: agent read models, stream callbacks, or empty success responses.
 * - Side effects: HTTP requests, SSE stream consumption, and auth-token cleanup on unauthorized stream responses.
 */

import { clearStoredAuthToken, getStoredAuthToken } from "../../features/auth/storage";
import type {
  AgentDraftAttachment,
  AgentDashboard,
  AgentDashboardRangeKey,
  AgentChangeItem,
  AgentRun,
  AgentStreamEvent,
  AgentThread,
  AgentThreadDetail,
  AgentThreadSummary,
  AgentToolCall
} from "../types";
import { API_BASE_URL, ApiError, extractErrorMessage, request } from "./core";

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
  if (!parsedBlock || !parsedBlock.eventType) {
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

function buildAgentMessageFormData(
  content: string,
  files: File[],
  modelName?: string | null,
  attachmentIds: string[] = []
): FormData {
  const formData = new FormData();
  formData.set("content", content);
  const normalizedModelName = modelName?.trim();
  if (normalizedModelName) {
    formData.set("model_name", normalizedModelName);
  }
  attachmentIds.forEach((attachmentId) => {
    formData.append("attachment_ids", attachmentId);
  });
  files.forEach((file) => {
    formData.append("files", file);
  });
  return formData;
}

function buildAgentDashboardQueryString(payload: {
  range: AgentDashboardRangeKey;
  models: string[];
  surfaces: string[];
}): string {
  const params = new URLSearchParams();
  params.set("range", payload.range);
  payload.models.forEach((modelName) => {
    params.append("model", modelName);
  });
  payload.surfaces.forEach((surface) => {
    params.append("surface", surface);
  });
  return params.toString();
}

export function listAgentThreads(): Promise<AgentThreadSummary[]> {
  return request<AgentThreadSummary[]>("/api/v1/agent/threads");
}

export function getAgentDashboard(payload: {
  range: AgentDashboardRangeKey;
  models: string[];
  surfaces: string[];
}): Promise<AgentDashboard> {
  return request<AgentDashboard>(`/api/v1/agent/dashboard?${buildAgentDashboardQueryString(payload)}`);
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

export function renameAgentThread(payload: { threadId: string; title: string }): Promise<AgentThread> {
  return request<AgentThread>(`/api/v1/agent/threads/${payload.threadId}`, {
    method: "PATCH",
    body: JSON.stringify({ title: payload.title })
  });
}

export function deleteAgentThread(threadId: string): Promise<void> {
  return request<void>(`/api/v1/agent/threads/${threadId}`, {
    method: "DELETE"
  });
}

export function sendAgentMessage(payload: {
  threadId: string;
  content: string;
  files: File[];
  attachmentIds?: string[];
  modelName?: string | null;
}): Promise<AgentRun> {
  return request<AgentRun>(`/api/v1/agent/threads/${payload.threadId}/messages`, {
    method: "POST",
    body: buildAgentMessageFormData(payload.content, payload.files, payload.modelName, payload.attachmentIds ?? [])
  });
}

export async function streamAgentMessage(payload: {
  threadId: string;
  content: string;
  files: File[];
  attachmentIds?: string[];
  modelName?: string | null;
  signal?: AbortSignal;
  onEvent: (event: AgentStreamEvent) => void;
}): Promise<void> {
  const token = getStoredAuthToken();
  if (!token) {
    throw new Error("Log in before calling the API.");
  }
  const response = await fetch(`${API_BASE_URL}/api/v1/agent/threads/${payload.threadId}/messages/stream`, {
    method: "POST",
    body: buildAgentMessageFormData(payload.content, payload.files, payload.modelName, payload.attachmentIds ?? []),
    signal: payload.signal,
    headers: {
      Accept: "text/event-stream",
      Authorization: `Bearer ${token}`
    }
  });
  if (!response.ok) {
    const body = await response.text();
    const message = extractErrorMessage(body, response.status);
    if (response.status === 401) {
      clearStoredAuthToken();
    }
    throw new ApiError(message, response.status);
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

export async function uploadAgentDraftAttachment(payload: {
  file: File;
  onUploadProgress?: (progressPercent: number) => void;
  onParsingStart?: () => void;
  signal?: AbortSignal;
}): Promise<AgentDraftAttachment> {
  const token = getStoredAuthToken();
  if (!token) {
    throw new Error("Log in before calling the API.");
  }

  return await new Promise<AgentDraftAttachment>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.set("file", payload.file);

    const cleanupAbortListener = () => {
      if (payload.signal) {
        payload.signal.removeEventListener("abort", handleAbort);
      }
    };

    function handleAbort() {
      xhr.abort();
    }

    xhr.open("POST", `${API_BASE_URL}/api/v1/agent/draft-attachments`);
    xhr.responseType = "text";
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) {
        return;
      }
      payload.onUploadProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    };

    xhr.upload.onload = () => {
      payload.onUploadProgress?.(100);
      payload.onParsingStart?.();
    };

    xhr.onerror = () => {
      cleanupAbortListener();
      reject(new Error("Attachment upload failed."));
    };

    xhr.onabort = () => {
      cleanupAbortListener();
      reject(new DOMException("The operation was aborted.", "AbortError"));
    };

    xhr.onload = () => {
      cleanupAbortListener();
      const responseText = typeof xhr.responseText === "string" ? xhr.responseText : "";
      if (xhr.status < 200 || xhr.status >= 300) {
        const message = extractErrorMessage(responseText, xhr.status);
        if (xhr.status === 401) {
          clearStoredAuthToken();
        }
        reject(new ApiError(message, xhr.status));
        return;
      }
      try {
        resolve(JSON.parse(responseText) as AgentDraftAttachment);
      } catch {
        reject(new Error("Attachment upload returned invalid JSON."));
      }
    };

    if (payload.signal) {
      if (payload.signal.aborted) {
        xhr.abort();
        return;
      }
      payload.signal.addEventListener("abort", handleAbort, { once: true });
    }

    xhr.send(formData);
  });
}

export function deleteAgentDraftAttachment(attachmentId: string): Promise<void> {
  return request<void>(`/api/v1/agent/draft-attachments/${attachmentId}`, {
    method: "DELETE"
  });
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

export function rejectAgentChangeItem(payload: {
  itemId: string;
  note?: string;
  payload_override?: Record<string, unknown>;
}): Promise<AgentChangeItem> {
  return request<AgentChangeItem>(`/api/v1/agent/change-items/${payload.itemId}/reject`, {
    method: "POST",
    body: JSON.stringify({
      note: payload.note,
      payload_override: payload.payload_override
    })
  });
}

export function reopenAgentChangeItem(payload: {
  itemId: string;
  note?: string;
  payload_override?: Record<string, unknown>;
}): Promise<AgentChangeItem> {
  return request<AgentChangeItem>(`/api/v1/agent/change-items/${payload.itemId}/reopen`, {
    method: "POST",
    body: JSON.stringify({
      note: payload.note,
      payload_override: payload.payload_override
    })
  });
}

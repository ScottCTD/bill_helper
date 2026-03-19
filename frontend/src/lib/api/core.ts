/**
 * CALLING SPEC:
 * - Purpose: provide the shared request layer for frontend API modules.
 * - Inputs: API path strings, request init objects, and auth token storage.
 * - Outputs: typed JSON responses or structured API errors.
 * - Side effects: network requests and auth-token cleanup on unauthorized responses.
 */

import { clearStoredAuthToken, getStoredAuthToken } from "../../features/auth/storage";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function extractErrorMessage(body: string, status: number): string {
  if (!body) {
    return `Request failed (${status})`;
  }

  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      return parsed.detail;
    }
  } catch {
    // Non-JSON error bodies fall back to raw text.
  }

  return body;
}

function buildApiHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers ?? {});
  const token = getStoredAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = buildApiHeaders(init);
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
    const message = extractErrorMessage(body, response.status);
    if (response.status === 401) {
      clearStoredAuthToken();
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  const headers = buildApiHeaders(init);
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers,
    ...init
  });

  if (!response.ok) {
    const body = await response.text();
    const message = extractErrorMessage(body, response.status);
    if (response.status === 401) {
      clearStoredAuthToken();
    }
    throw new ApiError(message, response.status);
  }

  return await response.blob();
}

export function withApiBase(path: string): string {
  return `${API_BASE_URL}${path}`;
}

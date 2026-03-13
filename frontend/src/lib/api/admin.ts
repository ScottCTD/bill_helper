/**
 * CALLING SPEC:
 * - Purpose: expose admin user and session API calls for the frontend.
 * - Inputs: admin user ids and admin-management payloads.
 * - Outputs: admin users, auth responses, session lists, or empty success responses.
 * - Side effects: HTTP requests only.
 */

import type { AdminSession, AuthLoginResponse, User } from "../types";
import { request } from "./core";

export function listAdminUsers(): Promise<User[]> {
  return request<User[]>("/api/v1/admin/users");
}

export function createAdminUser(payload: {
  name: string;
  password: string;
  is_admin: boolean;
}): Promise<User> {
  return request<User>("/api/v1/admin/users", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateAdminUser(
  userId: string,
  payload: {
    name?: string;
    is_admin?: boolean;
  }
): Promise<User> {
  return request<User>(`/api/v1/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function resetAdminUserPassword(
  userId: string,
  payload: { new_password: string }
): Promise<User> {
  return request<User>(`/api/v1/admin/users/${userId}/reset-password`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function deleteAdminUser(userId: string): Promise<void> {
  return request<void>(`/api/v1/admin/users/${userId}`, {
    method: "DELETE"
  });
}

export function loginAsAdminUser(userId: string): Promise<AuthLoginResponse> {
  return request<AuthLoginResponse>(`/api/v1/admin/users/${userId}/login-as`, {
    method: "POST"
  });
}

export function listAdminSessions(): Promise<AdminSession[]> {
  return request<AdminSession[]>("/api/v1/admin/sessions");
}

export function deleteAdminSession(sessionId: string): Promise<void> {
  return request<void>(`/api/v1/admin/sessions/${sessionId}`, {
    method: "DELETE"
  });
}

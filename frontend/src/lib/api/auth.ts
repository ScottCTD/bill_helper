/**
 * CALLING SPEC:
 * - Purpose: expose authentication API calls for the frontend.
 * - Inputs: login credentials and password-change payloads.
 * - Outputs: auth session responses or empty success responses.
 * - Side effects: HTTP requests only.
 */

import type { AuthLoginResponse, AuthSession } from "../types";
import { request } from "./core";

export function login(payload: { username: string; password: string }): Promise<AuthLoginResponse> {
  return request<AuthLoginResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function logout(): Promise<void> {
  return request<void>("/api/v1/auth/logout", {
    method: "POST"
  });
}

export function getAuthSession(): Promise<AuthSession> {
  return request<AuthSession>("/api/v1/auth/me");
}

export function changeMyPassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  return request<void>("/api/v1/users/me/change-password", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

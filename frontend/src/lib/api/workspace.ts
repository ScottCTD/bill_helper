/**
 * CALLING SPEC:
 * - Purpose: expose per-user workspace snapshot and lifecycle API calls for the frontend.
 * - Inputs: no inputs for the current-user snapshot; explicit lifecycle actions for start/stop.
 * - Outputs: workspace snapshot read models and IDE launch metadata.
 * - Side effects: HTTP requests only.
 */

import type { WorkspaceIdeSession, WorkspaceSnapshot } from "../types";
import { request } from "./core";

export function getWorkspaceSnapshot(): Promise<WorkspaceSnapshot> {
  return request<WorkspaceSnapshot>("/api/v1/workspace");
}

export function startWorkspace(): Promise<WorkspaceSnapshot> {
  return request<WorkspaceSnapshot>("/api/v1/workspace/start", {
    method: "POST"
  });
}

export function stopWorkspace(): Promise<WorkspaceSnapshot> {
  return request<WorkspaceSnapshot>("/api/v1/workspace/stop", {
    method: "POST"
  });
}

export function createWorkspaceIdeSession(): Promise<WorkspaceIdeSession> {
  return request<WorkspaceIdeSession>("/api/v1/workspace/ide/session", {
    method: "POST"
  });
}

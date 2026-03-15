/**
 * CALLING SPEC:
 * - Purpose: define workspace lifecycle and file-tree contracts for the frontend.
 * - Inputs: frontend modules that render the current user's workspace state.
 * - Outputs: workspace-domain interfaces.
 * - Side effects: type declarations only.
 */

export interface WorkspaceSnapshot {
  workspace_enabled: boolean;
  starts_on_login: boolean;
  status: string;
  container_name: string;
  volume_name: string;
  ide_ready: boolean;
  ide_launch_path: string;
  degraded_reason: string | null;
}

export interface WorkspaceIdeSession {
  launch_url: string;
  snapshot: WorkspaceSnapshot;
}

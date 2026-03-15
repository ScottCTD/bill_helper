/**
 * CALLING SPEC:
 * - Purpose: render the `WorkspacePage` React UI module.
 * - Inputs: callers that import `frontend/src/pages/WorkspacePage.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `WorkspacePage`.
 * - Side effects: React rendering and user event wiring.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FolderTree,
  Loader2,
  MonitorSmartphone,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { Button } from "../components/ui/button";
import {
  createWorkspaceIdeSession,
  getWorkspaceSnapshot,
  withApiBase,
} from "../lib/api";
import { queryKeys } from "../lib/queryKeys";
import type { WorkspaceSnapshot } from "../lib/types";
import { cn } from "../lib/utils";

const NARROW_WORKSPACE_MEDIA_QUERY = "(max-width: 960px)";

interface WorkspacePageProps {
  isActive?: boolean;
}

export function WorkspacePage({ isActive = true }: WorkspacePageProps) {
  const queryClient = useQueryClient();
  const [launchUrl, setLaunchUrl] = useState<string | null>(null);
  const [launchError, setLaunchError] = useState<string | null>(null);
  const [isIdeFrameLoaded, setIsIdeFrameLoaded] = useState(false);
  const [isNarrowViewport, setIsNarrowViewport] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.matchMedia(NARROW_WORKSPACE_MEDIA_QUERY).matches;
  });
  const autoLaunchAttemptedRef = useRef<string | null>(null);
  const hasActivatedWorkspaceRef = useRef(isActive);

  if (isActive) {
    hasActivatedWorkspaceRef.current = true;
  }

  const shouldInitializeWorkspace = isActive || hasActivatedWorkspaceRef.current || launchUrl !== null;

  const workspaceQuery = useQuery({
    queryKey: queryKeys.workspace.snapshot,
    queryFn: getWorkspaceSnapshot,
    enabled: shouldInitializeWorkspace,
  });

  const launchMutation = useMutation({
    mutationFn: createWorkspaceIdeSession,
    onSuccess: (payload) => {
      queryClient.setQueryData(queryKeys.workspace.snapshot, payload.snapshot);
      setIsIdeFrameLoaded(false);
      setLaunchUrl(withApiBase(payload.launch_url));
      setLaunchError(null);
    },
    onError: (error) => {
      setLaunchError((error as Error).message);
    }
  });

  const snapshot = workspaceQuery.data;
  const workspaceStatus = useMemo(
    () => (snapshot ? describeWorkspaceStatus(snapshot) : null),
    [snapshot]
  );
  const mobileFallback = isNarrowViewport;
  const effectiveLaunchError = launchError ?? snapshot?.degraded_reason ?? null;

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }
    const mediaQuery = window.matchMedia(NARROW_WORKSPACE_MEDIA_QUERY);
    const listener = (event: MediaQueryListEvent) => {
      setIsNarrowViewport(event.matches);
    };
    setIsNarrowViewport(mediaQuery.matches);
    mediaQuery.addEventListener("change", listener);
    return () => {
      mediaQuery.removeEventListener("change", listener);
    };
  }, []);

  useEffect(() => {
    if (!launchUrl) {
      setIsIdeFrameLoaded(false);
    }
  }, [launchUrl]);

  useEffect(() => {
    if (!isActive && launchUrl === null) {
      return;
    }
    if (!snapshot) {
      return;
    }
    if (autoLaunchAttemptedRef.current === snapshot.container_name) {
      return;
    }
    if (mobileFallback || !canLaunchWorkspace(snapshot)) {
      autoLaunchAttemptedRef.current = snapshot.container_name;
      return;
    }
    autoLaunchAttemptedRef.current = snapshot.container_name;
    setLaunchError(null);
    launchMutation.mutate();
  }, [launchMutation, mobileFallback, snapshot]);

  const canLaunch = snapshot ? canLaunchWorkspace(snapshot) : false;
  const launchPending = launchMutation.isPending;
  const showLiveIde = Boolean(!mobileFallback && launchUrl && !effectiveLaunchError);
  const showLoadingSpinner =
    workspaceQuery.isLoading || launchPending || (showLiveIde && !isIdeFrameLoaded);
  const shouldShowRetryAction = Boolean(
    snapshot &&
      effectiveLaunchError &&
      !mobileFallback &&
      canLaunch &&
      snapshot.status !== "image_missing" &&
      snapshot.status !== "provisioning_error"
  );

  return (
    <div
      className={cn(
        "workspace-ide-page",
        !isActive && "workspace-ide-page-hidden",
      )}
      aria-hidden={!isActive}
    >
      <div className="workspace-ide-layout">
        <section className="workspace-ide-stage">
          {showLiveIde ? (
            <iframe
              key={launchUrl ?? "workspace-ide"}
              className={cn(
                "workspace-ide-frame",
                !isIdeFrameLoaded && "workspace-ide-frame-loading",
              )}
              src={launchUrl ?? undefined}
              title="Workspace IDE"
              onLoad={() => {
                setIsIdeFrameLoaded(true);
              }}
            />
          ) : null}

          {showLoadingSpinner ? (
            <WorkspaceLoadingSpinner
              label={workspaceQuery.isLoading ? "Loading workspace" : "Loading workspace IDE"}
              description={
                workspaceQuery.isLoading
                  ? "Reading the current sandbox status and canonical file mounts."
                  : "Starting the browser IDE and waiting for the editor to finish booting."
              }
            />
          ) : null}

          {!showLoadingSpinner && workspaceQuery.error ? (
            <WorkspaceStageShell>
              <WorkspaceStageState
                title="Workspace unavailable"
                description={(workspaceQuery.error as Error).message}
                tone="error"
              />
            </WorkspaceStageShell>
          ) : null}

          {!showLoadingSpinner && snapshot ? (
            <>
              {mobileFallback ? (
                <WorkspaceStageShell>
                  <WorkspaceStageState
                    icon={<MonitorSmartphone className="h-5 w-5" />}
                    title="Workspace IDE is desktop-first"
                    description="Use a wider viewport for the embedded editor."
                    tone="warning"
                  />
                </WorkspaceStageShell>
              ) : null}

              {!mobileFallback && !showLiveIde ? (
                <WorkspaceStageShell>
                  <WorkspaceStageState
                    icon={<FolderTree className="h-5 w-5" />}
                    title={workspaceStatus?.label ?? "Workspace"}
                    description={effectiveLaunchError ?? workspaceStatus?.detail ?? "Start the workspace IDE to continue."}
                    tone={workspaceStatus?.tone === "danger" ? "error" : workspaceStatus?.tone === "warning" ? "warning" : "default"}
                    action={
                      shouldShowRetryAction ? (
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => {
                            setLaunchError(null);
                            launchMutation.mutate();
                          }}
                        >
                          Retry launch
                        </Button>
                      ) : null
                    }
                  />
                </WorkspaceStageShell>
              ) : null}
            </>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function WorkspaceStageState({
  title,
  description,
  tone = "default",
  icon,
  action,
}: {
  title: string;
  description: string;
  tone?: "default" | "warning" | "error";
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div
      className={cn(
        "workspace-ide-stage-state",
        tone === "warning" && "workspace-ide-stage-state-warning",
        tone === "error" && "workspace-ide-stage-state-error",
      )}
    >
      {icon ? <div className="workspace-ide-stage-icon">{icon}</div> : null}
      <div className="workspace-ide-stage-copy">
        <p className="workspace-ide-stage-title">{title}</p>
        <p className="workspace-ide-stage-description">{description}</p>
        {action ? <div className="workspace-ide-stage-action">{action}</div> : null}
      </div>
    </div>
  );
}

function WorkspaceStageShell({ children }: { children: ReactNode }) {
  return <div className="workspace-ide-stage-shell">{children}</div>;
}

function WorkspaceLoadingSpinner({
  label,
  description,
}: {
  label: string;
  description: string;
}) {
  return (
    <div
      className="workspace-ide-loading-shell"
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <div className="workspace-ide-loading-card">
        <Loader2 className="workspace-ide-loading-spinner" />
        <div className="workspace-ide-loading-copy">
          <p className="workspace-ide-loading-title">{label}</p>
          <p className="workspace-ide-loading-description">{description}</p>
        </div>
      </div>
    </div>
  );
}

function describeWorkspaceStatus(snapshot: WorkspaceSnapshot): {
  label: string;
  detail: string;
  tone: "default" | "success" | "warning" | "danger";
} {
  if (!snapshot.workspace_enabled || snapshot.status === "disabled") {
    return {
      label: "Disabled",
      detail: "Provisioning is off in backend config.",
      tone: "warning"
    };
  }
  if (snapshot.status === "running" && snapshot.ide_ready) {
    return {
      label: "Live",
      detail: "The workspace container and IDE endpoint are ready.",
      tone: "success"
    };
  }
  if (snapshot.status === "running") {
    return {
      label: "Starting",
      detail: "The container is running and the IDE is still coming up.",
      tone: "default"
    };
  }
  if (snapshot.status === "created") {
    return {
      label: "Provisioned",
      detail: "The container definition exists and is ready to start.",
      tone: "default"
    };
  }
  if (snapshot.status === "missing") {
    return {
      label: "Missing",
      detail: "Workspace resources are missing and need reprovisioning.",
      tone: "danger"
    };
  }
  if (snapshot.status === "image_missing") {
    return {
      label: "Image missing",
      detail: "Build the configured Docker image before starting the workspace.",
      tone: "danger"
    };
  }
  if (snapshot.status === "provisioning_error") {
    return {
      label: "Provisioning error",
      detail: snapshot.degraded_reason ?? "The backend could not provision the workspace.",
      tone: "danger"
    };
  }
  return {
    label: snapshot.status,
    detail: snapshot.degraded_reason ?? "Workspace status changed outside the standard lifecycle.",
    tone: "default"
  };
}

function canLaunchWorkspace(snapshot: WorkspaceSnapshot): boolean {
  if (!snapshot.workspace_enabled) {
    return false;
  }
  return snapshot.status !== "image_missing" && snapshot.status !== "provisioning_error";
}

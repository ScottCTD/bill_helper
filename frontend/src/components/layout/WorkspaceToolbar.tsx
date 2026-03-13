/**
 * CALLING SPEC:
 * - Purpose: render the `WorkspaceToolbar` React UI module.
 * - Inputs: callers that import `frontend/src/components/layout/WorkspaceToolbar.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `WorkspaceToolbar`.
 * - Side effects: React rendering and user event wiring.
 */
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface WorkspaceToolbarProps {
  className?: string;
  children: ReactNode;
}

export function WorkspaceToolbar({ className, children }: WorkspaceToolbarProps) {
  return <div className={cn("workspace-toolbar", className)}>{children}</div>;
}

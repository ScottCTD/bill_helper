import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface WorkspaceToolbarProps {
  className?: string;
  children: ReactNode;
}

export function WorkspaceToolbar({ className, children }: WorkspaceToolbarProps) {
  return <div className={cn("workspace-toolbar", className)}>{children}</div>;
}

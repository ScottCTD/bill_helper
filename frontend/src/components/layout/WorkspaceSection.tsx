/**
 * CALLING SPEC:
 * - Purpose: render the `WorkspaceSection` React UI module.
 * - Inputs: callers that import `frontend/src/components/layout/WorkspaceSection.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `WorkspaceSection`.
 * - Side effects: React rendering and user event wiring.
 */
import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { cn } from "../../lib/utils";

interface WorkspaceSectionProps {
  title?: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
  contentClassName?: string;
  children: ReactNode;
}

export function WorkspaceSection({
  title,
  description,
  actions,
  className,
  contentClassName,
  children
}: WorkspaceSectionProps) {
  const hasHeader = Boolean(title || description || actions);

  return (
    <Card className={cn("workspace-section", className)}>
      {hasHeader ? (
        <CardHeader className="workspace-section-header">
          <div className="workspace-section-copy">
            {title ? <CardTitle className="workspace-section-title">{title}</CardTitle> : null}
            {description ? <p className="workspace-section-description">{description}</p> : null}
          </div>
          {actions ? <div className="workspace-section-actions">{actions}</div> : null}
        </CardHeader>
      ) : null}
      <CardContent className={cn("workspace-section-body", !hasHeader && "pt-5", contentClassName)}>{children}</CardContent>
    </Card>
  );
}

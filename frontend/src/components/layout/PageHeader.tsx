/**
 * CALLING SPEC:
 * - Purpose: render the `PageHeader` React UI module.
 * - Inputs: callers that import `frontend/src/components/layout/PageHeader.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `PageHeader`.
 * - Side effects: React rendering and user event wiring.
 */
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  kicker?: string;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({ title, description, kicker, actions, className }: PageHeaderProps) {
  return (
    <header className={cn("page-header", className)}>
      <div className="page-header-copy">
        {kicker ? <p className="page-kicker">{kicker}</p> : null}
        <div className="page-heading">
          <h1 className="page-title">{title}</h1>
          {description ? <p className="page-description">{description}</p> : null}
        </div>
      </div>
      {actions ? <div className="page-header-actions">{actions}</div> : null}
    </header>
  );
}

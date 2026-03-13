/**
 * CALLING SPEC:
 * - Purpose: render the `EmptyState` React UI module.
 * - Inputs: callers that import `frontend/src/components/layout/EmptyState.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `EmptyState`.
 * - Side effects: React rendering and user event wiring.
 */
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface EmptyStateProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, actions, className }: EmptyStateProps) {
  return (
    <section className={cn("empty-state", className)}>
      <div className="empty-state-copy">
        <p className="empty-state-title">{title}</p>
        {description ? <p className="empty-state-description">{description}</p> : null}
      </div>
      {actions ? <div className="empty-state-actions">{actions}</div> : null}
    </section>
  );
}

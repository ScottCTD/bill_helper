/**
 * CALLING SPEC:
 * - Purpose: render the `StatBlock` React UI module.
 * - Inputs: callers that import `frontend/src/components/layout/StatBlock.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `StatBlock`.
 * - Side effects: React rendering and user event wiring.
 */
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

type StatBlockTone = "default" | "success" | "warning" | "danger";

interface StatBlockProps {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  tone?: StatBlockTone;
  className?: string;
}

export function StatBlock({ label, value, detail, tone = "default", className }: StatBlockProps) {
  return (
    <section className={cn("stat-block", `stat-block-${tone}`, className)}>
      <p className="stat-block-label">{label}</p>
      <p className="stat-block-value">{value}</p>
      {detail ? <p className="stat-block-detail">{detail}</p> : null}
    </section>
  );
}

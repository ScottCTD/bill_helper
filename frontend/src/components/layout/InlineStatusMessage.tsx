/**
 * CALLING SPEC:
 * - Purpose: render the `InlineStatusMessage` React UI module.
 * - Inputs: callers that import `frontend/src/components/layout/InlineStatusMessage.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `InlineStatusMessage`.
 * - Side effects: React rendering and user event wiring.
 */
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

type InlineStatusTone = "neutral" | "success" | "warning" | "error";

interface InlineStatusMessageProps {
  tone?: InlineStatusTone;
  className?: string;
  children: ReactNode;
}

export function InlineStatusMessage({ tone = "neutral", className, children }: InlineStatusMessageProps) {
  return <p className={cn("inline-status", `inline-status-${tone}`, className)}>{children}</p>;
}

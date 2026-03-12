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

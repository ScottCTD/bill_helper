/**
 * CALLING SPEC:
 * - Purpose: render the `tooltip` React UI module.
 * - Inputs: callers that import `frontend/src/components/ui/tooltip.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `tooltip`.
 * - Side effects: React rendering and user event wiring.
 */
import { type ReactNode, useId, useState } from "react";

import { cn } from "../../lib/utils";

interface TooltipProps {
  content: string;
  children: ReactNode;
}

export function Tooltip({ content, children }: TooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const tooltipId = useId();

  return (
    <span
      className="tooltip-root"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
      onFocus={() => setIsOpen(true)}
      onBlur={() => setIsOpen(false)}
    >
      <span aria-describedby={isOpen ? tooltipId : undefined}>{children}</span>
      <span
        id={tooltipId}
        role="tooltip"
        aria-hidden={!isOpen}
        className={cn("tooltip-content", isOpen && "tooltip-content-open")}
      >
        {content}
      </span>
    </span>
  );
}

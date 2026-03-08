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

/**
 * CALLING SPEC:
 * - Purpose: render the `native-select` React UI module.
 * - Inputs: callers that import `frontend/src/components/ui/native-select.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `native-select`.
 * - Side effects: React rendering and user event wiring.
 */
import * as React from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "../../lib/utils";

interface NativeSelectProps extends React.ComponentProps<"select"> {
  wrapperClassName?: string;
}

const NativeSelect = React.forwardRef<HTMLSelectElement, NativeSelectProps>(({ className, wrapperClassName, children, ...props }, ref) => (
  <div className={cn("relative w-full", wrapperClassName)}>
    <select
      ref={ref}
      className={cn(
        "flex h-10 w-full appearance-none items-center rounded-md border border-input bg-background px-3 py-2 pr-8 text-sm text-foreground shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:bg-muted/50 disabled:opacity-60",
        className
      )}
      {...props}
    >
      {children}
    </select>
    <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
  </div>
));
NativeSelect.displayName = "NativeSelect";

export { NativeSelect };

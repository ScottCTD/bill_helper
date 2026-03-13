/**
 * CALLING SPEC:
 * - Purpose: render the `badge` React UI module.
 * - Inputs: callers that import `frontend/src/components/ui/badge.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `badge`.
 * - Side effects: React rendering and user event wiring.
 */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-primary/20 bg-primary/10 text-foreground hover:bg-primary/15",
        secondary: "border-border/80 bg-secondary text-secondary-foreground hover:bg-accent",
        destructive: "border-destructive/20 bg-destructive/10 text-destructive hover:bg-destructive/15",
        outline: "border-border/80 bg-background text-foreground"
      }
    },
    defaultVariants: {
      variant: "default"
    }
  }
);

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };

import * as React from "react";

import { cn } from "../../lib/utils";
import { Label } from "./label";

interface FormFieldProps extends React.HTMLAttributes<HTMLLabelElement> {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string | null;
}

export function FormField({ className, label, htmlFor, hint, error, children, ...props }: FormFieldProps) {
  return (
    <label className={cn("grid gap-2 text-sm", className)} htmlFor={htmlFor} {...props}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error ? <p className="text-xs font-medium text-destructive">{error}</p> : null}
      {!error && hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </label>
  );
}

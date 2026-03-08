import { Trash2 } from "lucide-react";

import { cn } from "../lib/utils";
import { Button, type ButtonProps } from "./ui/button";

interface DeleteIconButtonProps extends Omit<ButtonProps, "children" | "aria-label" | "title"> {
  label: string;
}

export function DeleteIconButton({ label, className, type = "button", variant = "ghost", size = "icon", ...buttonProps }: DeleteIconButtonProps) {
  return (
    <Button
      type={type}
      variant={variant}
      size={size}
      className={cn(
        "h-8 w-8 shrink-0 rounded-md p-0 text-muted-foreground shadow-none hover:bg-destructive/10 hover:text-destructive",
        className
      )}
      aria-label={label}
      title={label}
      {...buttonProps}
    >
      <Trash2 className="h-4 w-4" aria-hidden="true" />
    </Button>
  );
}
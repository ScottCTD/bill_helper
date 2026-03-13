/**
 * CALLING SPEC:
 * - Purpose: provide the `utils` frontend module.
 * - Inputs: callers that import `frontend/src/lib/utils.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `utils`.
 * - Side effects: module-local frontend behavior only.
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

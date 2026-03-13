/**
 * CALLING SPEC:
 * - Purpose: provide the `tagColors` frontend module.
 * - Inputs: callers that import `frontend/src/lib/tagColors.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `tagColors`.
 * - Side effects: module-local frontend behavior only.
 */
export function fallbackTagColor(tagName: string) {
  let hash = 0;
  for (let index = 0; index < tagName.length; index += 1) {
    hash = (hash * 31 + tagName.charCodeAt(index)) >>> 0;
  }
  const hue = hash % 360;
  return `hsl(${hue} 62% 72%)`;
}

export function resolveTagColor(name: string, color: string | null | undefined) {
  return color ?? fallbackTagColor(name);
}
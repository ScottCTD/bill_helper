/**
 * CALLING SPEC:
 * - Purpose: open attachment previews in a browser-native new tab.
 * - Inputs: callers that import `frontend/src/features/agent/panel/attachmentBrowserOpen.ts` and pass a resolved preview URL.
 * - Outputs: helper exports from `attachmentBrowserOpen`.
 * - Side effects: opens a browser tab/window.
 */
export function openAttachmentInNewTab(previewUrl: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.open(previewUrl, "_blank", "noopener,noreferrer");
}

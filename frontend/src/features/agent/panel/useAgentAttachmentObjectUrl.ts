/**
 * CALLING SPEC:
 * - Purpose: provide authenticated object URLs for persisted agent attachment previews.
 * - Inputs: callers that import `frontend/src/features/agent/panel/useAgentAttachmentObjectUrl.ts` and pass an attachment URL.
 * - Outputs: hook state describing the resolved object URL and fetch status.
 * - Side effects: authenticated attachment fetches and object URL lifecycle management.
 */
import { useEffect, useState } from "react";

import { requestBlob } from "../../../lib/api/core";

interface AgentAttachmentObjectUrlState {
  hasFailed: boolean;
  objectUrl: string | null;
}

export function useAgentAttachmentObjectUrl(attachmentUrl: string): AgentAttachmentObjectUrlState {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [hasFailed, setHasFailed] = useState(false);

  useEffect(() => {
    const abortController = new AbortController();
    let isActive = true;
    let nextObjectUrl: string | null = null;
    setObjectUrl(null);
    setHasFailed(false);

    void (async () => {
      try {
        const blob = await requestBlob(attachmentUrl, { signal: abortController.signal });
        nextObjectUrl = URL.createObjectURL(blob);
        if (!isActive) {
          URL.revokeObjectURL(nextObjectUrl);
          nextObjectUrl = null;
          return;
        }
        setObjectUrl(nextObjectUrl);
      } catch (error) {
        if (!isActive || (error as Error).name === "AbortError") {
          return;
        }
        setHasFailed(true);
      }
    })();

    return () => {
      isActive = false;
      abortController.abort();
      if (nextObjectUrl) {
        URL.revokeObjectURL(nextObjectUrl);
      }
    };
  }, [attachmentUrl]);

  return {
    hasFailed,
    objectUrl
  };
}

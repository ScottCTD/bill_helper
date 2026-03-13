/**
 * CALLING SPEC:
 * - Purpose: provide the `modalTypes` frontend module.
 * - Inputs: callers that import `frontend/src/features/agent/review/modalTypes.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `modalTypes`.
 * - Side effects: module-local frontend behavior only.
 */
import type { AgentChangeItem, AgentRun } from "../../../lib/types";

export interface AgentThreadReviewModalProps {
  open: boolean;
  runs: AgentRun[];
  onOpenChange: (open: boolean) => void;
  onApproveItem: (payload: { itemId: string; payloadOverride?: Record<string, unknown> }) => Promise<AgentChangeItem>;
  onRejectItem: (payload: { itemId: string; payloadOverride?: Record<string, unknown> }) => Promise<AgentChangeItem>;
  onReopenItem: (payload: { itemId: string; payloadOverride?: Record<string, unknown> }) => Promise<AgentChangeItem>;
  isBusy?: boolean;
}

export interface BatchSummary {
  action: "approve" | "reject";
  succeeded: number;
  failed: number;
  failedItemIds: string[];
}

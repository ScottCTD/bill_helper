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

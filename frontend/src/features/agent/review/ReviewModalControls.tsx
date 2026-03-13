/**
 * CALLING SPEC:
 * - Purpose: render the `ReviewModalControls` React UI module.
 * - Inputs: callers that import `frontend/src/features/agent/review/ReviewModalControls.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `ReviewModalControls`.
 * - Side effects: React rendering and user event wiring.
 */
import { PanelLeft, PanelLeftClose } from "lucide-react";

import { Button } from "../../../components/ui/button";
import type { AgentThreadReviewController } from "./useAgentThreadReviewController";

interface ReviewModalControlsProps {
  controller: Pick<
    AgentThreadReviewController,
    | "activeItemId"
    | "activeReviewItem"
    | "handleApproveActive"
    | "handleBatchAction"
    | "handleRejectActive"
    | "handleReopenActive"
    | "isActiveEditable"
    | "isActivePending"
    | "isBatchRunning"
    | "isSidebarCollapsed"
    | "items"
    | "nextPendingItemId"
    | "pendingCount"
    | "selectRelativeItem"
    | "setActiveItemId"
    | "toggleSidebar"
  >;
  isBusy?: boolean;
}

export function ReviewModalControls({ controller, isBusy = false }: ReviewModalControlsProps) {
  return (
    <div className="agent-review-controls-bar">
      <div className="agent-review-controls-group">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="agent-review-sidebar-toggle"
          onClick={controller.toggleSidebar}
          aria-controls="agent-review-sidebar"
          aria-expanded={!controller.isSidebarCollapsed}
        >
          {controller.isSidebarCollapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          {controller.isSidebarCollapsed ? "Show list" : "Hide list"}
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={() => {
            void controller.handleBatchAction("approve");
          }}
          disabled={controller.pendingCount === 0 || controller.isBatchRunning || isBusy}
        >
          {controller.isBatchRunning ? "Working..." : "Approve All"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            void controller.handleBatchAction("reject");
          }}
          disabled={controller.pendingCount === 0 || controller.isBatchRunning || isBusy}
        >
          {controller.isBatchRunning ? "Working..." : "Reject All"}
        </Button>
      </div>

      <div className="agent-review-controls-group agent-review-controls-nav">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => controller.selectRelativeItem(-1)}
          disabled={controller.items.length <= 1}
        >
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => controller.selectRelativeItem(1)}
          disabled={controller.items.length <= 1}
        >
          Next
        </Button>
        {controller.isActivePending ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => controller.setActiveItemId(controller.nextPendingItemId)}
            disabled={!controller.nextPendingItemId || controller.nextPendingItemId === controller.activeItemId}
          >
            Skip
          </Button>
        ) : null}
      </div>

      {controller.isActivePending ? (
        <div className="agent-review-controls-group agent-review-controls-actions">
          <Button type="button" variant="outline" onClick={controller.handleRejectActive} disabled={isBusy || controller.isBatchRunning}>
            Reject
          </Button>
          <Button type="button" onClick={controller.handleApproveActive} disabled={isBusy || controller.isBatchRunning}>
            Approve
          </Button>
        </div>
      ) : controller.isActiveEditable ? (
        <div className="agent-review-controls-group agent-review-controls-actions">
          {controller.activeReviewItem?.item.status !== "PENDING_REVIEW" ? (
            <Button type="button" variant="ghost" onClick={controller.handleReopenActive} disabled={isBusy || controller.isBatchRunning}>
              Move to Pending
            </Button>
          ) : null}
          <Button type="button" variant="outline" onClick={controller.handleRejectActive} disabled={isBusy || controller.isBatchRunning}>
            {controller.activeReviewItem?.item.status === "REJECTED" ? "Save Rejected" : "Reject"}
          </Button>
          <Button type="button" onClick={controller.handleApproveActive} disabled={isBusy || controller.isBatchRunning}>
            {controller.activeReviewItem?.item.status === "APPLY_FAILED" ? "Approve Again" : "Approve"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

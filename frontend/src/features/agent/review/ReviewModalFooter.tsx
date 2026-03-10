import { Button } from "../../../components/ui/button";
import { shortId } from "./model";
import type { AgentThreadReviewController } from "./useAgentThreadReviewController";

interface ReviewModalFooterProps {
  controller: Pick<
    AgentThreadReviewController,
    "actionError" | "actionNotice" | "activeReviewItem" | "batchSummary" | "items" | "pendingCount" | "setActiveItemId"
  >;
}

export function ReviewModalFooter({ controller }: ReviewModalFooterProps) {
  return (
    <footer className="agent-review-modal-footer">
      <p className="agent-review-footer-pending">
        Pending {controller.pendingCount} of {controller.items.length}
        {controller.activeReviewItem ? ` · Run ${controller.activeReviewItem.runIndex}` : ""}
      </p>
      {controller.actionError ? <p className="error agent-review-footer-message">{controller.actionError}</p> : null}
      {controller.actionNotice ? <p className="muted agent-review-footer-message">{controller.actionNotice}</p> : null}
      {controller.batchSummary ? (
        <div className="agent-review-batch-summary">
          <p>
            {controller.batchSummary.action === "approve" ? "Approved" : "Rejected"} {controller.batchSummary.succeeded} · Failed{" "}
            {controller.batchSummary.failed}
          </p>
          {controller.batchSummary.failedItemIds.length > 0 ? (
            <div className="agent-review-failed-links">
              {controller.batchSummary.failedItemIds.map((itemId) => (
                <Button key={itemId} type="button" variant="link" size="sm" onClick={() => controller.setActiveItemId(itemId)}>
                  Jump to {shortId(itemId)}
                </Button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </footer>
  );
}

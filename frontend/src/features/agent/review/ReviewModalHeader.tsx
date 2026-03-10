import { Badge } from "../../../components/ui/badge";
import { DialogDescription, DialogHeader, DialogTitle } from "../../../components/ui/dialog";
import type { AgentThreadReviewController } from "./useAgentThreadReviewController";

interface ReviewModalHeaderProps {
  controller: Pick<AgentThreadReviewController, "items" | "pendingCount" | "resolvedItems">;
}

export function ReviewModalHeader({ controller }: ReviewModalHeaderProps) {
  return (
    <DialogHeader className="agent-review-modal-header">
      <div className="agent-review-header-copy">
        <DialogTitle>Thread review</DialogTitle>
        <DialogDescription>
          {controller.pendingCount} pending of {controller.items.length} proposal{controller.items.length === 1 ? "" : "s"}
        </DialogDescription>
      </div>
      <div className="agent-review-header-stats">
        <Badge variant="outline" className="agent-review-header-pill">
          Pending {controller.pendingCount}
        </Badge>
        <Badge variant="outline" className="agent-review-header-pill">
          Reviewed {controller.resolvedItems.length}
        </Badge>
      </div>
    </DialogHeader>
  );
}

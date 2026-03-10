import { Dialog, DialogContent } from "../../../components/ui/dialog";
import { cn } from "../../../lib/utils";
import { ReviewTocSection } from "./ReviewEditors";
import { ReviewActiveItemCard } from "./ReviewActiveItemCard";
import { ReviewModalControls } from "./ReviewModalControls";
import { ReviewModalFooter } from "./ReviewModalFooter";
import { ReviewModalHeader } from "./ReviewModalHeader";
import type { AgentThreadReviewModalProps } from "./modalTypes";
import { useAgentThreadReviewController } from "./useAgentThreadReviewController";

export function AgentThreadReviewModal(props: AgentThreadReviewModalProps) {
  const controller = useAgentThreadReviewController(props);

  if (!props.open) {
    return null;
  }

  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent className="agent-review-modal-content h-[96vh] w-[96vw] max-w-none overflow-hidden bg-card p-0 sm:w-[94vw] md:w-[92vw] lg:h-[94vh] lg:w-[88vw] xl:w-[78rem]">
        <div className="agent-review-modal-layout">
          <ReviewModalHeader controller={controller} />

          <div className={cn("agent-review-shell", controller.isSidebarCollapsed && "is-sidebar-collapsed")}>
            <ReviewModalControls controller={controller} isBusy={props.isBusy} />

            {!controller.isSidebarCollapsed ? (
              <aside id="agent-review-sidebar" className="agent-review-sidebar">
                <div className="agent-review-sidebar-scroll">
                  <ReviewTocSection
                    title="Pending"
                    items={controller.pendingItems}
                    activeItemId={controller.activeItemId}
                    onSelect={controller.setActiveItemId}
                  />
                  <ReviewTocSection
                    title="Reviewed / Failed"
                    items={controller.resolvedItems}
                    activeItemId={controller.activeItemId}
                    onSelect={controller.setActiveItemId}
                  />
                </div>
              </aside>
            ) : null}

            <section className="agent-review-card-column">
              <ReviewActiveItemCard controller={controller} isBusy={props.isBusy} />
            </section>
          </div>

          <ReviewModalFooter controller={controller} />
        </div>
      </DialogContent>
    </Dialog>
  );
}

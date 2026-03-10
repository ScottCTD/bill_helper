import { PanelRight, PanelRightClose } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { AgentAttachmentPreviewDialog } from "./panel/AgentAttachmentPreviewDialog";
import { AgentComposer } from "./panel/AgentComposer";
import { AgentThreadPanel } from "./panel/AgentThreadPanel";
import { AgentThreadUsageBar } from "./panel/AgentThreadUsageBar";
import { AgentTimeline } from "./panel/AgentTimeline";
import { useAgentPanelController } from "./panel/useAgentPanelController";
import { AgentThreadReviewModal } from "./review/AgentThreadReviewModal";

interface AgentPanelProps {
  isOpen: boolean;
  onClose?: () => void;
}

export function AgentPanel({ isOpen }: AgentPanelProps) {
  const controller = useAgentPanelController({ isOpen });

  if (!isOpen) {
    return null;
  }

  return (
    <>
      <aside className="agent-panel agent-panel-page" aria-label="Agent panel">
        <header className="agent-panel-header">
          <div className="agent-panel-header-top">
            <h2>Bill Assistant</h2>
            <div className="agent-panel-header-actions">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={controller.header.openReview}
                disabled={
                  !controller.header.selectedThreadId ||
                  controller.header.reviewProposalCount === 0 ||
                  controller.header.isMutating ||
                  controller.header.isBulkLaunching
                }
                className={`agent-panel-review-button${controller.header.pendingReviewCount > 0 ? " is-pending" : ""}`}
              >
                <span>Review</span>
                {controller.header.pendingReviewCount > 0 ? (
                  <Badge variant="outline" className="agent-panel-review-badge">
                    {controller.header.pendingReviewCount}
                  </Badge>
                ) : null}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={controller.header.createThread}
                disabled={controller.header.isMutating || controller.header.isBulkLaunching}
              >
                New Thread
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={controller.header.toggleThreadPanel}
                title={controller.header.isThreadPanelOpen ? "Collapse threads" : "Expand threads"}
              >
                {controller.header.isThreadPanelOpen ? (
                  <PanelRightClose className="h-4 w-4" />
                ) : (
                  <PanelRight className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
          <AgentThreadUsageBar
            selectedThreadId={controller.header.selectedThreadId}
            totals={controller.header.threadUsageTotals}
          />
        </header>

        <div className="agent-panel-body agent-panel-body-page">
          <section className="agent-thread-timeline agent-thread-main">
            <AgentTimeline {...controller.timeline} />

            <AgentComposer {...controller.composer} />
          </section>

          {controller.threadPanel.isOpen ? (
            <div
              className="panel-resize-handle agent-resize-handle"
              onMouseDown={controller.threadPanel.handleResizeMouseDown}
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize threads panel"
            />
          ) : null}

          <div
            className={controller.threadPanel.slotClassName}
            style={controller.threadPanel.isOpen ? { width: controller.threadPanel.panelWidth } : undefined}
          >
            <AgentThreadPanel
              threads={controller.threadPanel.threads}
              selectedThreadId={controller.threadPanel.selectedThreadId}
              isLoading={controller.threadPanel.isLoading}
              errorMessage={controller.threadPanel.errorMessage}
              onSelectThread={controller.threadPanel.onSelectThread}
              onRenameThread={controller.threadPanel.onRenameThread}
              onDeleteThread={controller.threadPanel.onDeleteThread}
              renamingThreadId={controller.threadPanel.renamingThreadId}
              deletingThreadId={controller.threadPanel.deletingThreadId}
              deleteDisabledThreadIds={controller.threadPanel.deleteDisabledThreadIds}
              renameDisabledThreadIds={controller.threadPanel.renameDisabledThreadIds}
              isOpen={controller.threadPanel.isOpen}
              optimisticRunningThreadIds={controller.threadPanel.optimisticRunningThreadIds}
            />
          </div>
        </div>

        <AgentThreadReviewModal {...controller.reviewModal} />
      </aside>

      <AgentAttachmentPreviewDialog {...controller.previewDialog} />
    </>
  );
}

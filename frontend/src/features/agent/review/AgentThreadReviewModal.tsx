import { PanelLeft, PanelLeftClose } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../../../components/ui/dialog";
import { cn } from "../../../lib/utils";
import {
  ReviewAccountEditor,
  ReviewEntityEditor,
  ReviewEntryEditor,
  ReviewGroupEditor,
  ReviewGroupMembershipEditor,
  ReviewTagEditor,
  ReviewTocSection
} from "./ReviewEditors";
import { buildReviewHeading, prettyDateTime, reviewModeClass, statusBadgeClass } from "./modalHelpers";
import type { AgentThreadReviewModalProps } from "./modalTypes";
import { buildReviewItemSummary, changeTypeLabel, shortId } from "./model";
import { useAgentThreadReviewController } from "./useAgentThreadReviewController";

export function AgentThreadReviewModal(props: AgentThreadReviewModalProps) {
  const controller = useAgentThreadReviewController(props);
  const activeReviewItem = controller.activeReviewItem;
  const diffPreview = controller.diffPreview;

  if (!props.open) {
    return null;
  }

  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent className="agent-review-modal-content h-[96vh] w-[96vw] max-w-none overflow-hidden bg-card p-0 sm:w-[94vw] md:w-[92vw] lg:h-[94vh] lg:w-[88vw] xl:w-[78rem]">
        <div className="agent-review-modal-layout">
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

          <div className={cn("agent-review-shell", controller.isSidebarCollapsed && "is-sidebar-collapsed")}>
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
                  disabled={controller.pendingCount === 0 || controller.isBatchRunning || props.isBusy}
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
                  disabled={controller.pendingCount === 0 || controller.isBatchRunning || props.isBusy}
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
                  <Button type="button" variant="outline" onClick={controller.handleRejectActive} disabled={props.isBusy || controller.isBatchRunning}>
                    Reject
                  </Button>
                  <Button type="button" onClick={controller.handleApproveActive} disabled={props.isBusy || controller.isBatchRunning}>
                    Approve
                  </Button>
                </div>
              ) : controller.isActiveEditable ? (
                <div className="agent-review-controls-group agent-review-controls-actions">
                  {controller.activeReviewItem?.item.status !== "PENDING_REVIEW" ? (
                    <Button type="button" variant="ghost" onClick={controller.handleReopenActive} disabled={props.isBusy || controller.isBatchRunning}>
                      Move to Pending
                    </Button>
                  ) : null}
                  <Button type="button" variant="outline" onClick={controller.handleRejectActive} disabled={props.isBusy || controller.isBatchRunning}>
                    {controller.activeReviewItem?.item.status === "REJECTED" ? "Save Rejected" : "Reject"}
                  </Button>
                  <Button type="button" onClick={controller.handleApproveActive} disabled={props.isBusy || controller.isBatchRunning}>
                    {controller.activeReviewItem?.item.status === "APPLY_FAILED" ? "Approve Again" : "Approve"}
                  </Button>
                </div>
              ) : null}
            </div>

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
              {!activeReviewItem || !diffPreview ? (
                <div className="agent-review-empty-card">
                  <p className="muted">{controller.items.length === 0 ? "No proposals in this thread." : "Select a proposal to review."}</p>
                </div>
              ) : (
                <article
                  key={activeReviewItem.item.id}
                  className={cn(
                    "agent-review-card",
                    reviewModeClass(activeReviewItem.item.change_type),
                    "agent-review-card-animated"
                  )}
                >
                  <header className="agent-review-card-header">
                    <div className="agent-review-card-header-main">
                      <div className="agent-review-card-kicker">
                        <span>{changeTypeLabel(activeReviewItem.item.change_type)}</span>
                        <Badge
                          variant="outline"
                          className={cn("agent-review-status-badge", statusBadgeClass(activeReviewItem.item.status))}
                        >
                          {activeReviewItem.item.status}
                        </Badge>
                      </div>
                      <h3>{buildReviewItemSummary(activeReviewItem.item)}</h3>
                      <p className="agent-review-card-run-meta">
                        Run {activeReviewItem.runIndex} · {prettyDateTime(activeReviewItem.runCreatedAt)} · Proposal {shortId(activeReviewItem.item.id)}
                      </p>
                    </div>
                  </header>

                  <div className="agent-review-card-body">
                    <section className="agent-review-panel-section">
                      <h4>Rationale</h4>
                      <p className="agent-review-rationale">{activeReviewItem.item.rationale_text || "No rationale provided."}</p>
                    </section>

                    <section className="agent-review-panel-section">
                      <div className="agent-review-section-heading">
                        <h4>{diffPreview.title}</h4>
                        <div className="agent-review-item-stats">
                          {diffPreview.stats.changed > 0 ? (
                            <Badge variant="outline" className="agent-review-diff-stat is-changed">
                              Changed {diffPreview.stats.changed}
                            </Badge>
                          ) : null}
                          {diffPreview.stats.added > 0 ? (
                            <Badge variant="outline" className="agent-review-diff-stat is-added">
                              Added {diffPreview.stats.added}
                            </Badge>
                          ) : null}
                          {diffPreview.stats.removed > 0 ? (
                            <Badge variant="outline" className="agent-review-diff-stat is-removed">
                              Removed {diffPreview.stats.removed}
                            </Badge>
                          ) : null}
                          {diffPreview.stats.changed === 0 &&
                          diffPreview.stats.added === 0 &&
                          diffPreview.stats.removed === 0 ? (
                            <Badge variant="outline" className="agent-review-diff-stat">
                              No deltas
                            </Badge>
                          ) : null}
                        </div>
                      </div>
                      {diffPreview.metadata.length > 0 ? (
                        <div
                          className="agent-review-metadata"
                          role="list"
                          aria-label={`Metadata for proposal ${shortId(activeReviewItem.item.id)}`}
                        >
                          {diffPreview.metadata.map((meta) => (
                            <div
                              key={`${activeReviewItem.item.id}:${meta.label}:${meta.value}`}
                              className={cn(
                                "agent-review-metadata-pill",
                                meta.tone === "warning" && "is-warning",
                                meta.tone === "danger" && "is-danger"
                              )}
                              role="listitem"
                            >
                              <span className="agent-review-metadata-label">{meta.label}</span>
                              <span className="agent-review-metadata-value">{meta.value}</span>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      <div className="agent-review-diff" role="list" aria-label={`Diff for proposal ${shortId(activeReviewItem.item.id)}`}>
                        {diffPreview.lines.length === 0 ? <p className="muted">No changed fields.</p> : null}
                        {diffPreview.lines.map((line) => (
                          <div
                            key={`${activeReviewItem.item.id}:${line.sign}:${line.path}:${line.value}`}
                            className={cn("agent-review-diff-line", line.sign === "+" ? "is-added" : "is-removed")}
                            role="listitem"
                          >
                            <span className="agent-review-diff-sign" aria-hidden>
                              {line.sign}
                            </span>
                            <span className="agent-review-diff-path">{line.path}</span>
                            <code className="agent-review-diff-value">{line.value}</code>
                          </div>
                        ))}
                      </div>
                      {diffPreview.note ? <p className="agent-review-item-note muted">{diffPreview.note}</p> : null}
                    </section>

                    {controller.editorResources.editorLoadError ? (
                      <p className="error agent-review-editor-error">
                        Review editor options failed to load: {controller.editorResources.editorLoadError}
                      </p>
                    ) : null}

                    {controller.isActiveEditable && controller.activeDrafts.activeEntryDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>{buildReviewHeading(controller.isActivePending, "entry")}</p>
                        </div>
                        <ReviewEntryEditor
                          draft={controller.activeDrafts.activeEntryDraft}
                          currencies={controller.editorResources.currencies}
                          entities={controller.editorResources.entities}
                          tags={controller.editorResources.tags}
                          validationError={controller.activeOverrideState.validationError}
                          isDisabled={props.isBusy || controller.isBatchRunning}
                          onDraftChange={controller.setActiveEntryDraft}
                        />
                      </section>
                    ) : null}

                    {controller.isActiveEditable && controller.activeDrafts.activeTagDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>{buildReviewHeading(controller.isActivePending, "tag")}</p>
                        </div>
                        <ReviewTagEditor
                          draft={controller.activeDrafts.activeTagDraft}
                          typeOptions={controller.editorResources.tagTypeOptions}
                          validationError={controller.activeOverrideState.validationError}
                          isDisabled={props.isBusy || controller.isBatchRunning}
                          onDraftChange={controller.setActiveTagDraft}
                        />
                      </section>
                    ) : null}

                    {controller.isActiveEditable && controller.activeDrafts.activeAccountDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>{buildReviewHeading(controller.isActivePending, "account")}</p>
                        </div>
                        <ReviewAccountEditor
                          draft={controller.activeDrafts.activeAccountDraft}
                          currencies={controller.editorResources.currencies}
                          validationError={controller.activeOverrideState.validationError}
                          isDisabled={props.isBusy || controller.isBatchRunning}
                          onDraftChange={controller.setActiveAccountDraft}
                        />
                      </section>
                    ) : null}

                    {controller.isActiveEditable && controller.activeDrafts.activeEntityDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>{buildReviewHeading(controller.isActivePending, "entity")}</p>
                        </div>
                        <ReviewEntityEditor
                          draft={controller.activeDrafts.activeEntityDraft}
                          categoryOptions={controller.editorResources.entityCategoryOptions}
                          validationError={controller.activeOverrideState.validationError}
                          isDisabled={props.isBusy || controller.isBatchRunning}
                          onDraftChange={controller.setActiveEntityDraft}
                        />
                      </section>
                    ) : null}

                    {controller.isActiveEditable && controller.activeDrafts.activeGroupDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>
                            {controller.isActivePending
                              ? activeReviewItem.item.change_type === "create_group"
                                ? "Adjust the proposed group before approval."
                                : "Rename the proposed group before approval."
                              : "Adjust the proposal payload before changing review status."}
                          </p>
                        </div>
                        <ReviewGroupEditor
                          draft={controller.activeDrafts.activeGroupDraft}
                          isUpdate={activeReviewItem.item.change_type === "update_group"}
                          validationError={controller.activeOverrideState.validationError}
                          isDisabled={props.isBusy || controller.isBatchRunning}
                          onDraftChange={controller.setActiveGroupDraft}
                        />
                      </section>
                    ) : null}

                    {controller.isActiveEditable && controller.activeDrafts.activeGroupMembershipDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>
                            {controller.isActivePending
                              ? "Review the group and member details before approval. Only split role is editable; unresolved proposal dependencies stay locked."
                              : "Review the group and member details before changing review status. Only split role is editable; unresolved proposal dependencies stay locked."}
                          </p>
                        </div>
                        <ReviewGroupMembershipEditor
                          item={activeReviewItem.item}
                          draft={controller.activeDrafts.activeGroupMembershipDraft}
                          validationError={controller.activeOverrideState.validationError}
                          isDisabled={props.isBusy || controller.isBatchRunning}
                          items={controller.items}
                          currencies={controller.editorResources.currencies}
                          entities={controller.editorResources.entities}
                          tags={controller.editorResources.tags}
                          defaultCurrencyCode={controller.editorResources.defaultCurrencyCode}
                          onDraftChange={controller.setActiveGroupMembershipDraft}
                        />
                      </section>
                    ) : null}

                    {controller.isActiveEditable &&
                    (activeReviewItem.item.change_type === "delete_group" ||
                      activeReviewItem.item.change_type === "delete_group_member") ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Confirmation</h4>
                          <p>This proposal is confirmation-only. Approve to apply exactly what is shown above.</p>
                        </div>
                        <p className="agent-review-rationale">
                          {activeReviewItem.item.change_type === "delete_group"
                            ? "Delete-group proposals are not reviewer-editable in v1."
                            : "Remove-member proposals are not reviewer-editable in v1."}
                        </p>
                      </section>
                    ) : null}

                    {!controller.isActivePending ? (
                      <section className="agent-review-panel-section">
                        <h4>Review outcome</h4>
                        {activeReviewItem.item.review_note ? (
                          <p className="agent-review-outcome-note">{activeReviewItem.item.review_note}</p>
                        ) : null}
                        {activeReviewItem.item.applied_resource_type && activeReviewItem.item.applied_resource_id ? (
                          <p className="muted">
                            Applied resource: {activeReviewItem.item.applied_resource_type} #{activeReviewItem.item.applied_resource_id}
                          </p>
                        ) : null}
                        {!activeReviewItem.item.review_note &&
                        !activeReviewItem.item.applied_resource_type &&
                        activeReviewItem.item.status !== "PENDING_REVIEW" ? (
                          <p className="muted">No additional review note recorded.</p>
                        ) : null}
                      </section>
                    ) : null}
                  </div>
                </article>
              )}
            </section>
          </div>

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
        </div>
      </DialogContent>
    </Dialog>
  );
}

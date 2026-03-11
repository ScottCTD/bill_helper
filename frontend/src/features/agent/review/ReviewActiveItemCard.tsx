import type { ReactNode } from "react";

import { Badge } from "../../../components/ui/badge";
import { formatMinor } from "../../../lib/format";
import { cn } from "../../../lib/utils";
import {
  ReviewAccountEditor,
  ReviewEntityEditor,
  ReviewEntryEditor,
  ReviewSnapshotEditor,
  ReviewGroupEditor,
  ReviewGroupMembershipEditor,
  ReviewTagEditor
} from "./ReviewEditors";
import { buildReviewHeading, prettyDateTime, reviewModeClass, statusBadgeClass } from "./modalHelpers";
import { buildReviewItemSummary, changeTypeLabel, shortId } from "./model";
import type { AgentThreadReviewController } from "./useAgentThreadReviewController";

interface ReviewActiveItemCardProps {
  controller: AgentThreadReviewController;
  isBusy?: boolean;
}

interface ReviewEditSectionProps {
  description: string;
  children: ReactNode;
}

function ReviewEditSection({ description, children }: ReviewEditSectionProps) {
  return (
    <section className="agent-review-panel-section">
      <div className="agent-review-section-heading">
        <h4>Review edits</h4>
        <p>{description}</p>
      </div>
      {children}
    </section>
  );
}

function SnapshotContextPanel({
  title,
  lines
}: {
  title: string;
  lines: string[];
}) {
  if (lines.length === 0) {
    return null;
  }
  return (
    <section className="agent-review-panel-section">
      <div className="agent-review-section-heading">
        <h4>{title}</h4>
      </div>
      <div className="space-y-2 text-sm text-muted-foreground">
        {lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
    </section>
  );
}

export function ReviewActiveItemCard({ controller, isBusy = false }: ReviewActiveItemCardProps) {
  const activeReviewItem = controller.activeReviewItem;
  const diffPreview = controller.diffPreview;
  const snapshotReviewContext = controller.editorResources.snapshotReviewContext;

  if (!activeReviewItem || !diffPreview) {
    return (
      <div className="agent-review-empty-card">
        <p className="muted">{controller.items.length === 0 ? "No proposals in this thread." : "Select a proposal to review."}</p>
      </div>
    );
  }

  return (
    <article
      key={activeReviewItem.item.id}
      className={cn("agent-review-card", reviewModeClass(activeReviewItem.item.change_type), "agent-review-card-animated")}
    >
      <header className="agent-review-card-header">
        <div className="agent-review-card-header-main">
          <div className="agent-review-card-kicker">
            <span>{changeTypeLabel(activeReviewItem.item.change_type)}</span>
            <Badge variant="outline" className={cn("agent-review-status-badge", statusBadgeClass(activeReviewItem.item.status))}>
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
              {diffPreview.stats.changed === 0 && diffPreview.stats.added === 0 && diffPreview.stats.removed === 0 ? (
                <Badge variant="outline" className="agent-review-diff-stat">
                  No deltas
                </Badge>
              ) : null}
            </div>
          </div>
          {diffPreview.metadata.length > 0 ? (
            <div className="agent-review-metadata" role="list" aria-label={`Metadata for proposal ${shortId(activeReviewItem.item.id)}`}>
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
          <ReviewEditSection description={buildReviewHeading(controller.isActivePending, "entry")}>
            <ReviewEntryEditor
              draft={controller.activeDrafts.activeEntryDraft}
              currencies={controller.editorResources.currencies}
              entities={controller.editorResources.entities}
              tags={controller.editorResources.tags}
              validationError={controller.activeOverrideState.validationError}
              isDisabled={isBusy || controller.isBatchRunning}
              onDraftChange={controller.setActiveEntryDraft}
            />
          </ReviewEditSection>
        ) : null}

        {controller.isActiveEditable && controller.activeDrafts.activeTagDraft ? (
          <ReviewEditSection description={buildReviewHeading(controller.isActivePending, "tag")}>
            <ReviewTagEditor
              draft={controller.activeDrafts.activeTagDraft}
              typeOptions={controller.editorResources.tagTypeOptions}
              validationError={controller.activeOverrideState.validationError}
              isDisabled={isBusy || controller.isBatchRunning}
              onDraftChange={controller.setActiveTagDraft}
            />
          </ReviewEditSection>
        ) : null}

        {controller.isActiveEditable && controller.activeDrafts.activeAccountDraft ? (
          <ReviewEditSection description={buildReviewHeading(controller.isActivePending, "account")}>
            <ReviewAccountEditor
              draft={controller.activeDrafts.activeAccountDraft}
              currencies={controller.editorResources.currencies}
              validationError={controller.activeOverrideState.validationError}
              isDisabled={isBusy || controller.isBatchRunning}
              onDraftChange={controller.setActiveAccountDraft}
            />
          </ReviewEditSection>
        ) : null}

        {controller.isActiveEditable && controller.activeDrafts.activeSnapshotDraft ? (
          <ReviewEditSection description={buildReviewHeading(controller.isActivePending, "snapshot")}>
            <ReviewSnapshotEditor
              draft={controller.activeDrafts.activeSnapshotDraft}
              accountName={snapshotReviewContext.accountName ?? "Unknown account"}
              currencyCode={snapshotReviewContext.currencyCode ?? "USD"}
              validationError={controller.activeOverrideState.validationError}
              isDisabled={isBusy || controller.isBatchRunning}
              onDraftChange={controller.setActiveSnapshotDraft}
            />
          </ReviewEditSection>
        ) : null}

        {activeReviewItem.item.change_type === "create_snapshot" ? (
          <SnapshotContextPanel
            title="Nearby snapshots"
            lines={[
              snapshotReviewContext.previousSnapshot
                ? `Previous snapshot: ${snapshotReviewContext.previousSnapshot.snapshot_at} (${formatMinor(snapshotReviewContext.previousSnapshot.balance_minor, snapshotReviewContext.currencyCode ?? "USD")})`
                : "Previous snapshot: none",
              snapshotReviewContext.nextSnapshot
                ? `Next snapshot: ${snapshotReviewContext.nextSnapshot.snapshot_at} (${formatMinor(snapshotReviewContext.nextSnapshot.balance_minor, snapshotReviewContext.currencyCode ?? "USD")})`
                : "Next snapshot: none",
              ...(snapshotReviewContext.reconciliationSummary ? [snapshotReviewContext.reconciliationSummary] : []),
              ...(snapshotReviewContext.loadError ? [`Context load error: ${snapshotReviewContext.loadError}`] : [])
            ]}
          />
        ) : null}

        {controller.isActiveEditable && controller.activeDrafts.activeEntityDraft ? (
          <ReviewEditSection description={buildReviewHeading(controller.isActivePending, "entity")}>
            <ReviewEntityEditor
              draft={controller.activeDrafts.activeEntityDraft}
              categoryOptions={controller.editorResources.entityCategoryOptions}
              validationError={controller.activeOverrideState.validationError}
              isDisabled={isBusy || controller.isBatchRunning}
              onDraftChange={controller.setActiveEntityDraft}
            />
          </ReviewEditSection>
        ) : null}

        {controller.isActiveEditable && controller.activeDrafts.activeGroupDraft ? (
          <ReviewEditSection
            description={
              controller.isActivePending
                ? activeReviewItem.item.change_type === "create_group"
                  ? "Adjust the proposed group before approval."
                  : "Rename the proposed group before approval."
                : "Adjust the proposal payload before changing review status."
            }
          >
            <ReviewGroupEditor
              draft={controller.activeDrafts.activeGroupDraft}
              isUpdate={activeReviewItem.item.change_type === "update_group"}
              validationError={controller.activeOverrideState.validationError}
              isDisabled={isBusy || controller.isBatchRunning}
              onDraftChange={controller.setActiveGroupDraft}
            />
          </ReviewEditSection>
        ) : null}

        {controller.isActiveEditable && controller.activeDrafts.activeGroupMembershipDraft ? (
          <ReviewEditSection
            description={
              controller.isActivePending
                ? "Review the group and member details before approval. Only split role is editable; unresolved proposal dependencies stay locked."
                : "Review the group and member details before changing review status. Only split role is editable; unresolved proposal dependencies stay locked."
            }
          >
            <ReviewGroupMembershipEditor
              item={activeReviewItem.item}
              draft={controller.activeDrafts.activeGroupMembershipDraft}
              validationError={controller.activeOverrideState.validationError}
              isDisabled={isBusy || controller.isBatchRunning}
              items={controller.items}
              currencies={controller.editorResources.currencies}
              entities={controller.editorResources.entities}
              tags={controller.editorResources.tags}
              defaultCurrencyCode={controller.editorResources.defaultCurrencyCode}
              onDraftChange={controller.setActiveGroupMembershipDraft}
            />
          </ReviewEditSection>
        ) : null}

        {controller.isActiveEditable &&
        (activeReviewItem.item.change_type === "delete_group" || activeReviewItem.item.change_type === "delete_group_member") ? (
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

        {activeReviewItem.item.change_type === "delete_snapshot" ? (
          <section className="agent-review-panel-section">
            <div className="agent-review-section-heading">
              <h4>Impact</h4>
              <p>Deleting a snapshot changes the interval boundaries used for reconciliation.</p>
            </div>
            <div className="space-y-2 text-sm text-muted-foreground">
              {snapshotReviewContext.impactLines.map((line) => (
                <p key={line}>{line}</p>
              ))}
              {snapshotReviewContext.reconciliationSummary ? <p>{snapshotReviewContext.reconciliationSummary}</p> : null}
              {snapshotReviewContext.loadError ? <p>Context load error: {snapshotReviewContext.loadError}</p> : null}
            </div>
          </section>
        ) : null}

        {!controller.isActivePending ? (
          <section className="agent-review-panel-section">
            <h4>Review outcome</h4>
            {activeReviewItem.item.review_note ? <p className="agent-review-outcome-note">{activeReviewItem.item.review_note}</p> : null}
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
  );
}

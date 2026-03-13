/**
 * CALLING SPEC:
 * - Purpose: render the `ReviewTocSection` React UI module.
 * - Inputs: callers that import `frontend/src/features/agent/review/ReviewTocSection.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `ReviewTocSection`.
 * - Side effects: React rendering and user event wiring.
 */
import { Badge } from "../../../components/ui/badge";
import { cn } from "../../../lib/utils";
import {
  groupReviewItems,
  reviewModeClass,
  statusBadgeClass,
  tocStatusIndicator
} from "./modalHelpers";
import { buildReviewItemSummary, isPendingReviewStatus, shortId, type ThreadReviewItem } from "./model";

export function ReviewTocSection({
  title,
  items,
  activeItemId,
  onSelect
}: {
  title: string;
  items: ThreadReviewItem[];
  activeItemId: string | null;
  onSelect: (itemId: string) => void;
}) {
  if (items.length === 0) {
    return null;
  }

  const groups = groupReviewItems(items);

  return (
    <section className="agent-review-toc-section" aria-label={title}>
      <div className="agent-review-toc-section-header">
        <h3>{title}</h3>
        <span>{items.length}</span>
      </div>
      {groups.map((group) => (
        <div key={group.key} className="agent-review-toc-group">
          <div className="agent-review-toc-group-header">
            <h4>{group.label}</h4>
            <span>{group.items.length}</span>
          </div>
          <div className="agent-review-toc-list">
            {group.items.map((reviewItem) => {
              const isActive = reviewItem.item.id === activeItemId;
              const statusIndicator = tocStatusIndicator(reviewItem.item.status);
              return (
                <button
                  key={reviewItem.item.id}
                  type="button"
                  className={cn(
                    "agent-review-toc-item",
                    reviewModeClass(reviewItem.item.change_type),
                    isActive && "is-active",
                    !isPendingReviewStatus(reviewItem.item.status) && "is-resolved"
                  )}
                  onClick={() => onSelect(reviewItem.item.id)}
                >
                  <div className="agent-review-toc-item-copy">
                    <span className="agent-review-toc-item-title">{buildReviewItemSummary(reviewItem.item)}</span>
                    <span className="agent-review-toc-item-meta">
                      Run {reviewItem.runIndex} · {shortId(reviewItem.item.id)}
                    </span>
                  </div>
                  {statusIndicator ? (
                    <span
                      className={cn("agent-review-toc-status-indicator", statusIndicator.className)}
                      aria-label={statusIndicator.label}
                      title={statusIndicator.label}
                    >
                      <statusIndicator.icon className="h-3.5 w-3.5" aria-hidden />
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}

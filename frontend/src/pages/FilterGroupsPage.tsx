/**
 * CALLING SPEC:
 * - Purpose: render the `FilterGroupsPage` React UI module.
 * - Inputs: callers that import `frontend/src/pages/FilterGroupsPage.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `FilterGroupsPage`.
 * - Side effects: React rendering and user event wiring.
 */
import { Button } from "../components/ui/button";
import { PageHeader } from "../components/layout/PageHeader";
import { WorkspaceSection } from "../components/layout/WorkspaceSection";
import { FilterGroupsManager } from "../features/filterGroups/FilterGroupsManager";
import { useFilterGroupsPageModel } from "../features/filterGroups/useFilterGroupsPageModel";

export function FilterGroupsPage() {
  const model = useFilterGroupsPageModel();

  return (
    <div className="page stack-lg">
      <PageHeader
        title="Filters"
        description="Saved filter groups."
        actions={
          model.showHeaderSubmit ? (
            <Button type="button" disabled={!model.canSubmit} onClick={model.handleSubmit}>
              {model.isPending ? model.submitPendingLabel : model.submitLabel}
            </Button>
          ) : null
        }
      />

      <WorkspaceSection>
        <FilterGroupsManager model={model} />
      </WorkspaceSection>
    </div>
  );
}

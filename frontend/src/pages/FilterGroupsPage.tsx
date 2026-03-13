/**
 * CALLING SPEC:
 * - Purpose: render the `FilterGroupsPage` React UI module.
 * - Inputs: callers that import `frontend/src/pages/FilterGroupsPage.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `FilterGroupsPage`.
 * - Side effects: React rendering and user event wiring.
 */
import { PageHeader } from "../components/layout/PageHeader";
import { WorkspaceSection } from "../components/layout/WorkspaceSection";
import { FilterGroupsManager } from "../features/filterGroups/FilterGroupsManager";

export function FilterGroupsPage() {
  return (
    <div className="page stack-lg">
      <PageHeader
        title="Filters"
        description="Saved filter groups."
      />

      <WorkspaceSection>
        <FilterGroupsManager />
      </WorkspaceSection>
    </div>
  );
}

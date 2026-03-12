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

import { Card, CardContent } from "../components/ui/card";
import { FilterGroupsManager } from "../features/filterGroups/FilterGroupsManager";

export function FilterGroupsPage() {
  return (
    <div className="stack-lg">
      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="table-shell-header">
            <div>
              <h2 className="table-shell-title">Filter</h2>
              <p className="table-shell-subtitle">Manage saved filter groups and open matching entries directly from each definition.</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <FilterGroupsManager />
    </div>
  );
}

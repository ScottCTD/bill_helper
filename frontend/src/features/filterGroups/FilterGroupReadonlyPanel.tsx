/**
 * CALLING SPEC:
 * - Purpose: render the read-only system detail panel for computed filter groups.
 * - Inputs: callers that provide the selected saved filter-group read model.
 * - Outputs: React UI that explains why the group is system-managed and links to matching entries.
 * - Side effects: React rendering and navigation wiring.
 */
import { Link } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import type { FilterGroup } from "../../lib/types";

interface FilterGroupReadonlyPanelProps {
  filterGroup: FilterGroup;
}

export function FilterGroupReadonlyPanel({ filterGroup }: FilterGroupReadonlyPanelProps) {
  return (
    <Card className="min-w-0 border-border/90">
      <CardHeader className="grid gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="grid gap-2">
            <CardTitle>{filterGroup.name}</CardTitle>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">Default</Badge>
              <Badge variant="outline">System</Badge>
            </div>
          </div>
          <Button asChild type="button" variant="outline" size="sm">
            <Link to={`/entries?filter_group_id=${filterGroup.id}`}>View matching entries</Link>
          </Button>
        </div>
      </CardHeader>

      <CardContent className="grid gap-4">
        <div className="grid gap-2 rounded-2xl border border-border bg-secondary/25 p-4">
          <h3 className="text-sm font-semibold">Computed automatically</h3>
          <p className="text-sm text-muted-foreground">{filterGroup.description}</p>
        </div>

        <div className="grid gap-2 rounded-2xl border border-dashed border-border p-4">
          <h3 className="text-sm font-semibold">Matching rule</h3>
          <p className="text-sm text-muted-foreground">{filterGroup.rule_summary}</p>
        </div>
      </CardContent>
    </Card>
  );
}

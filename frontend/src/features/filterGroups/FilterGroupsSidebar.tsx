/**
 * CALLING SPEC:
 * - Purpose: render the selectable filter-group navigation list for the filters workspace.
 * - Inputs: callers that provide saved groups, selection state, and selection handlers.
 * - Outputs: React UI for the filter-group list.
 * - Side effects: React rendering and user event wiring.
 */
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import type { FilterGroup } from "../../lib/types";
import { cn } from "../../lib/utils";
import type { FilterGroupEditorTarget } from "./filterGroupEditorState";

interface FilterGroupsSidebarProps {
  filterGroups: FilterGroup[];
  selectedTarget: FilterGroupEditorTarget | null;
  onCreateNew: () => void;
  onSelectExisting: (filterGroupId: string) => void;
}

function FilterGroupsSidebarItem({
  label,
  description,
  color,
  badgeLabel,
  isActive,
  onClick
}: {
  label: string;
  description: string;
  color: string | null;
  badgeLabel: string;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={cn(
        "grid w-full gap-2 rounded-xl border p-3 text-left transition-colors",
        isActive ? "border-border bg-accent" : "border-border/80 bg-card hover:bg-secondary/35"
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span
            aria-hidden="true"
            className="mt-0.5 h-3 w-3 shrink-0 rounded-full border border-black/10"
            style={{ backgroundColor: color ?? "hsl(var(--muted))" }}
          />
          <span className="min-w-0 truncate text-sm font-medium text-foreground">{label}</span>
        </div>
        <Badge variant={isActive ? "secondary" : "outline"}>{badgeLabel}</Badge>
      </div>
      <p className="line-clamp-2 text-sm text-muted-foreground">{description}</p>
    </button>
  );
}

export function FilterGroupsSidebar({
  filterGroups,
  selectedTarget,
  onCreateNew,
  onSelectExisting
}: FilterGroupsSidebarProps) {
  const isDraftSelected = selectedTarget?.kind === "new";

  return (
    <div className="grid gap-4 rounded-2xl border border-border bg-card p-4">
      <div className="grid gap-2">
        <div className="grid gap-1">
          <h2 className="text-sm font-semibold">Filter groups</h2>
          <p className="text-sm text-muted-foreground">Pick one group to edit, or start a new custom group.</p>
        </div>
        <Button type="button" onClick={onCreateNew}>
          New custom group
        </Button>
      </div>

      <div className="grid gap-2">
        {isDraftSelected ? (
          <FilterGroupsSidebarItem
            label="New custom group"
            description="Unsaved draft"
            color={null}
            badgeLabel="Draft"
            isActive
            onClick={onCreateNew}
          />
        ) : null}

        {filterGroups.map((filterGroup) => (
          <FilterGroupsSidebarItem
            key={filterGroup.id}
            label={filterGroup.name}
            description={filterGroup.description ?? "No description yet."}
            color={filterGroup.color}
            badgeLabel={filterGroup.is_default ? "Default" : "Custom"}
            isActive={selectedTarget?.kind === "existing" && selectedTarget.filterGroupId === filterGroup.id}
            onClick={() => onSelectExisting(filterGroup.id)}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * CALLING SPEC:
 * - Purpose: render the filter-groups workspace body for the filters route.
 * - Inputs: callers that provide the page model for saved groups, selection state, and CRUD handlers.
 * - Outputs: React UI for the master-detail filter-group workspace.
 * - Side effects: React rendering and user event wiring.
 */
import { FilterGroupEditorPanel } from "./FilterGroupEditorPanel";
import { FilterGroupReadonlyPanel } from "./FilterGroupReadonlyPanel";
import { FilterGroupsSidebar } from "./FilterGroupsSidebar";
import { DiscardChangesDialog } from "./DiscardChangesDialog";
import type { FilterGroupsPageModel } from "./useFilterGroupsPageModel";

interface FilterGroupsManagerProps {
  model: FilterGroupsPageModel;
}

export function FilterGroupsManager({ model }: FilterGroupsManagerProps) {
  const existingSession = model.session?.kind === "existing" ? model.session : null;

  return (
    <>
      <div className="grid gap-4">
        <p className="muted text-sm">
          These rules drive dashboard classification and the saved group shortcut in entries. Pick a group on the left, edit it on the
          right, and use advanced mode only when you need nested logic.
        </p>

        {model.filterGroupsQuery.isError ? (
          <p className="error">Failed to load filter groups: {(model.filterGroupsQuery.error as Error).message}</p>
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
          <div className="xl:sticky xl:top-6 xl:self-start">
            <FilterGroupsSidebar
              filterGroups={model.filterGroups}
              selectedTarget={model.selectedTarget}
              onCreateNew={() => model.requestTarget({ kind: "new" })}
              onSelectExisting={(filterGroupId) => model.requestTarget({ kind: "existing", filterGroupId })}
            />
          </div>

          <div className="min-w-0">
            {model.filterGroupsQuery.isLoading && !model.session ? <p>Loading filter groups...</p> : null}

            {model.session ? (
              model.isSystemUntagged && model.selectedFilterGroup ? (
                <FilterGroupReadonlyPanel filterGroup={model.selectedFilterGroup} />
              ) : (
                <FilterGroupEditorPanel
                  key={model.session.kind === "new" ? "new" : model.session.filterGroupId}
                  session={model.session}
                  tags={model.tags}
                  preferredTagName={model.preferredTagName}
                  isDirty={model.isDirty}
                  isPending={model.isPending}
                  mutationError={model.mutationError}
                  tagLoadError={model.tagsQuery.isError ? (model.tagsQuery.error as Error).message : null}
                  onChange={model.updateFormState}
                  onDelete={existingSession && !existingSession.isDefault ? () => model.handleDelete(existingSession.filterGroupId) : undefined}
                />
              )
            ) : (
              <div className="rounded-2xl border border-dashed border-border bg-secondary/25 p-6 text-sm text-muted-foreground">
                No filter groups are available yet.
              </div>
            )}
          </div>
        </div>
      </div>

      <DiscardChangesDialog
        open={model.discardDialogOpen}
        onOpenChange={model.handleDiscardDialogOpenChange}
        onConfirm={model.confirmDiscardChanges}
      />
    </>
  );
}

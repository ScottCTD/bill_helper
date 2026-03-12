import { PageHeader } from "../components/layout/PageHeader";
import { WorkspaceSection } from "../components/layout/WorkspaceSection";
import { EntitiesTableSection } from "../features/entities/EntitiesTableSection";
import { useEntitiesPageModel } from "../features/entities/useEntitiesPageModel";

export function EntitiesPage() {
  const model = useEntitiesPageModel();
  const entitiesError = model.queries.entitiesQuery.isError ? (model.queries.entitiesQuery.error as Error).message : null;
  const createError = model.mutations.createEntityMutation.isError ? (model.mutations.createEntityMutation.error as Error).message : null;
  const updateError = model.mutations.updateEntityMutation.isError ? (model.mutations.updateEntityMutation.error as Error).message : null;
  const deleteError = model.mutations.deleteEntityMutation.isError ? (model.mutations.deleteEntityMutation.error as Error).message : null;

  return (
    <div className="page stack-lg">
      <PageHeader
        title="Entities"
        description="Counterparties and categories."
      />

      <WorkspaceSection>
        <EntitiesTableSection
          search={model.search}
          onSearchChange={model.setSearch}
          createPanelOpen={model.createPanelOpen}
          onToggleCreatePanel={() => model.setCreatePanelOpen((open) => !open)}
          onCloseCreatePanel={model.closeCreatePanel}
          newEntityName={model.forms.newEntityName}
          onNewEntityNameChange={model.forms.setNewEntityName}
          newEntityCategory={model.forms.newEntityCategory}
          onNewEntityCategoryChange={model.forms.setNewEntityCategory}
          editingEntityId={model.forms.editingEntityId}
          editingEntityName={model.forms.editingEntityName}
          onEditingEntityNameChange={model.forms.setEditingEntityName}
          editingEntityCategory={model.forms.editingEntityCategory}
          onEditingEntityCategoryChange={model.forms.setEditingEntityCategory}
          onStartEditEntity={model.actions.startEditEntity}
          onCancelEditEntity={model.actions.cancelEditEntity}
          onSaveEntity={model.actions.saveEntity}
          onStartDeleteEntity={model.actions.startDeleteEntity}
          onCancelDeleteEntity={model.actions.cancelDeleteEntity}
          onConfirmDeleteEntity={model.actions.confirmDeleteEntity}
          onCreateEntitySubmit={model.actions.onCreateEntity}
          entities={model.filteredEntities}
          deletingEntity={model.deletingEntity}
          hasAnyEntities={model.hasAnyEntities}
          entityCategoryOptions={model.entityCategoryOptions}
          isLoading={model.queries.entitiesQuery.isLoading}
          isError={model.queries.entitiesQuery.isError}
          queryErrorMessage={entitiesError}
          createErrorMessage={createError}
          updateErrorMessage={updateError}
          deleteErrorMessage={deleteError}
          isCreating={model.mutations.createEntityMutation.isPending}
          isUpdating={model.mutations.updateEntityMutation.isPending}
          isDeleting={model.mutations.deleteEntityMutation.isPending}
        />
      </WorkspaceSection>
    </div>
  );
}

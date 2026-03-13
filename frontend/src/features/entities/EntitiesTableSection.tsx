/**
 * CALLING SPEC:
 * - Purpose: render the `EntitiesTableSection` React UI module.
 * - Inputs: callers that import `frontend/src/features/entities/EntitiesTableSection.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `EntitiesTableSection`.
 * - Side effects: React rendering and user event wiring.
 */
import type { FormEvent } from "react";
import { Plus } from "lucide-react";

import { DeleteConfirmDialog } from "../../components/DeleteConfirmDialog";
import { DeleteIconButton } from "../../components/DeleteIconButton";
import { CreatableSingleSelect } from "../../components/CreatableSingleSelect";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "../../components/ui/dialog";
import { FormField } from "../../components/ui/form-field";
import { Input } from "../../components/ui/input";
import { formatMinor } from "../../lib/format";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import type { Entity } from "../../lib/types";

interface EntitiesTableSectionProps {
  search: string;
  onSearchChange: (value: string) => void;
  createPanelOpen: boolean;
  onToggleCreatePanel: () => void;
  onCloseCreatePanel: () => void;
  newEntityName: string;
  onNewEntityNameChange: (value: string) => void;
  newEntityCategory: string;
  onNewEntityCategoryChange: (value: string) => void;
  editingEntityId: string;
  editingEntityName: string;
  onEditingEntityNameChange: (value: string) => void;
  editingEntityCategory: string;
  onEditingEntityCategoryChange: (value: string) => void;
  onStartEditEntity: (entity: Entity) => void;
  onCancelEditEntity: () => void;
  onSaveEntity: (entityId: string) => void;
  onStartDeleteEntity: (entity: Entity) => void;
  onCancelDeleteEntity: () => void;
  onConfirmDeleteEntity: () => void;
  onCreateEntitySubmit: (event: FormEvent<HTMLFormElement>) => void;
  entities: Entity[] | undefined;
  deletingEntity: Entity | null;
  hasAnyEntities: boolean;
  entityCategoryOptions: string[];
  isLoading: boolean;
  isError: boolean;
  queryErrorMessage: string | null;
  createErrorMessage: string | null;
  updateErrorMessage: string | null;
  deleteErrorMessage: string | null;
  isCreating: boolean;
  isUpdating: boolean;
  isDeleting: boolean;
}

export function EntitiesTableSection(props: EntitiesTableSectionProps) {
  const {
    search,
    onSearchChange,
    createPanelOpen,
    onToggleCreatePanel,
    onCloseCreatePanel,
    newEntityName,
    onNewEntityNameChange,
    newEntityCategory,
    onNewEntityCategoryChange,
    editingEntityId,
    editingEntityName,
    onEditingEntityNameChange,
    editingEntityCategory,
    onEditingEntityCategoryChange,
    onStartEditEntity,
    onCancelEditEntity,
    onSaveEntity,
    onStartDeleteEntity,
    onCancelDeleteEntity,
    onConfirmDeleteEntity,
    onCreateEntitySubmit,
    entities,
    deletingEntity,
    hasAnyEntities,
    entityCategoryOptions,
    isLoading,
    isError,
    queryErrorMessage,
    createErrorMessage,
    updateErrorMessage,
    deleteErrorMessage,
    isCreating,
    isUpdating,
    isDeleting
  } = props;

  function netAmountLabel(entity: Entity): string {
    if (entity.net_amount_mixed_currencies) {
      return "Mixed currencies";
    }
    if (entity.net_amount_minor === null || entity.net_amount_minor === undefined || !entity.net_amount_currency_code) {
      return "-";
    }
    return formatMinor(entity.net_amount_minor, entity.net_amount_currency_code);
  }

  return (
    <div className="table-shell">
      <div className="table-toolbar">
        <div className="table-toolbar-filters">
          <label className="field min-w-[220px] grow">
            <span>Search</span>
            <Input placeholder="Filter by entity or category" value={search} onChange={(event) => onSearchChange(event.target.value)} />
          </label>
        </div>
        <div className="table-toolbar-action">
          <Button type="button" size="icon" variant="outline" aria-label="Add entity" onClick={onToggleCreatePanel}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isLoading ? <p>Loading entities...</p> : null}
      {isError ? <p className="error">{queryErrorMessage}</p> : null}

      {entities ? (
        entities.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Category</TableHead>
                <TableHead className="text-right">Net</TableHead>
                <TableHead className="icon-action-column">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entities.map((entity) => (
                <TableRow key={entity.id} className="cursor-pointer" onDoubleClick={() => onStartEditEntity(entity)}>
                  <TableCell>
                    <span className="entities-name">{entity.name}</span>
                  </TableCell>
                  <TableCell>{entity.category || "(none)"}</TableCell>
                  <TableCell className="text-right whitespace-nowrap">{netAmountLabel(entity)}</TableCell>
                  <TableCell className="icon-action-column">
                    <div className="table-actions">
                      <DeleteIconButton
                        label={`Delete entity ${entity.name}`}
                        onClick={() => onStartDeleteEntity(entity)}
                        onDoubleClick={(event) => event.stopPropagation()}
                      />
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="muted">{hasAnyEntities ? "No entities match the current search." : "No entities yet."}</p>
        )
      ) : null}

      <Dialog
        open={createPanelOpen}
        onOpenChange={(open) => {
          if (!open) {
            onCloseCreatePanel();
          }
        }}
      >
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Create Entity</DialogTitle>
            <DialogDescription>Add a named counterparty and optional category.</DialogDescription>
          </DialogHeader>
          <form className="grid gap-4" onSubmit={onCreateEntitySubmit}>
            <FormField label="Name">
              <Input placeholder="e.g. Landlord" value={newEntityName} onChange={(event) => onNewEntityNameChange(event.target.value)} />
            </FormField>
            <FormField label="Category">
              <CreatableSingleSelect
                value={newEntityCategory}
                options={entityCategoryOptions}
                ariaLabel="Entity category"
                placeholder="Select or create category..."
                onChange={onNewEntityCategoryChange}
              />
            </FormField>
            {createErrorMessage ? <p className="error">{createErrorMessage}</p> : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onCloseCreatePanel}>
                Cancel
              </Button>
              <Button type="submit" disabled={isCreating}>
                {isCreating ? "Creating..." : "Create"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(editingEntityId)}
        onOpenChange={(open) => {
          if (!open) {
            onCancelEditEntity();
          }
        }}
      >
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Edit Entity</DialogTitle>
            <DialogDescription>Update entity naming and category metadata.</DialogDescription>
          </DialogHeader>
          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (!editingEntityId) {
                return;
              }
              onSaveEntity(editingEntityId);
            }}
          >
            <FormField label="Name">
              <Input
                placeholder="e.g. Landlord"
                value={editingEntityName}
                onChange={(event) => onEditingEntityNameChange(event.target.value)}
              />
            </FormField>
            <FormField label="Category">
              <CreatableSingleSelect
                value={editingEntityCategory}
                options={entityCategoryOptions}
                ariaLabel="Edit entity category"
                placeholder="Select or create category..."
                onChange={onEditingEntityCategoryChange}
              />
            </FormField>
            {updateErrorMessage ? <p className="error">{updateErrorMessage}</p> : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onCancelEditEntity}>
                Cancel
              </Button>
              <Button type="submit" disabled={isUpdating || !editingEntityId}>
                {isUpdating ? "Saving..." : "Save"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <DeleteConfirmDialog
        open={Boolean(deletingEntity)}
        onOpenChange={(open) => {
          if (!open) {
            onCancelDeleteEntity();
          }
        }}
        title={deletingEntity ? `Delete ${deletingEntity.name}?` : "Delete entity?"}
        description="This removes the entity record. Existing entries keep the visible label text, but the linked entity becomes missing."
        confirmLabel="Delete entity"
        isPending={isDeleting}
        errorMessage={deleteErrorMessage}
        blockMessage={deletingEntity && (deletingEntity.account_count ?? 0) > 0 ? "Account-backed entities are managed from Accounts." : null}
        warnings={
          deletingEntity && (deletingEntity.entry_count ?? 0) > 0
            ? ["Entries that reference this entity stay in the ledger and show a missing-entity marker with the preserved label."]
            : []
        }
        onConfirm={onConfirmDeleteEntity}
      />
    </div>
  );
}

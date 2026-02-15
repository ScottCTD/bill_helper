import type { FormEvent } from "react";
import { Plus } from "lucide-react";

import type { Entity } from "../../../lib/types";
import { CreatableSingleSelect } from "../../../components/CreatableSingleSelect";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";

interface EntitiesSectionProps {
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
  onCreateEntitySubmit: (event: FormEvent<HTMLFormElement>) => void;
  entities: Entity[] | undefined;
  hasAnyEntities: boolean;
  entityCategoryOptions: string[];
  isLoading: boolean;
  isError: boolean;
  queryErrorMessage: string | null;
  createErrorMessage: string | null;
  updateErrorMessage: string | null;
  isCreating: boolean;
  isUpdating: boolean;
}

export function EntitiesSection(props: EntitiesSectionProps) {
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
    onCreateEntitySubmit,
    entities,
    hasAnyEntities,
    entityCategoryOptions,
    isLoading,
    isError,
    queryErrorMessage,
    createErrorMessage,
    updateErrorMessage,
    isCreating,
    isUpdating
  } = props;

  return (
    <div className="table-shell">
      <div className="table-shell-header">
        <div>
          <h3 className="table-shell-title">Entities</h3>
          <p className="table-shell-subtitle">Manage counterparties and assign taxonomy-backed categories.</p>
        </div>
      </div>
      <div className="table-toolbar">
        <div className="table-toolbar-filters">
          <label className="field min-w-[220px] grow">
            <span>Search</span>
            <Input placeholder="Filter by entity or category" value={search} onChange={(event) => onSearchChange(event.target.value)} />
          </label>
        </div>
        <div className="table-toolbar-action">
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label={createPanelOpen ? "Cancel add entity" : "Add entity"}
            onClick={onToggleCreatePanel}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {createPanelOpen ? (
        <form className="table-inline-form" onSubmit={onCreateEntitySubmit}>
          <label className="field min-w-[220px] grow">
            <span>Name</span>
            <Input placeholder="e.g. Landlord" value={newEntityName} onChange={(event) => onNewEntityNameChange(event.target.value)} />
          </label>
          <label className="field min-w-[220px] grow">
            <span>Category</span>
            <CreatableSingleSelect
              value={newEntityCategory}
              options={entityCategoryOptions}
              ariaLabel="Entity category"
              placeholder="Select or create category..."
              onChange={onNewEntityCategoryChange}
            />
          </label>
          <div className="table-inline-form-actions">
            <Button type="submit" size="sm" disabled={isCreating}>
              {isCreating ? "Creating..." : "Create"}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={onCloseCreatePanel}>
              Cancel
            </Button>
          </div>
        </form>
      ) : null}

      {createErrorMessage ? <p className="error">{createErrorMessage}</p> : null}
      {isLoading ? <p>Loading entities...</p> : null}
      {isError ? <p className="error">{queryErrorMessage}</p> : null}

      {entities ? (
        entities.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>From</TableHead>
                <TableHead>To</TableHead>
                <TableHead>Accounts</TableHead>
                <TableHead>Entries</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entities.map((entity) => (
                <TableRow key={entity.id}>
                  <TableCell>
                    {editingEntityId === entity.id ? (
                      <Input value={editingEntityName} className="h-8" onChange={(event) => onEditingEntityNameChange(event.target.value)} />
                    ) : (
                      entity.name
                    )}
                  </TableCell>
                  <TableCell>
                    {editingEntityId === entity.id ? (
                      <div className="min-w-[200px]">
                        <CreatableSingleSelect
                          value={editingEntityCategory}
                          options={entityCategoryOptions}
                          ariaLabel="Edit entity category"
                          placeholder="Select or create category..."
                          onChange={onEditingEntityCategoryChange}
                        />
                      </div>
                    ) : (
                      entity.category || "(none)"
                    )}
                  </TableCell>
                  <TableCell>{entity.from_count ?? 0}</TableCell>
                  <TableCell>{entity.to_count ?? 0}</TableCell>
                  <TableCell>{entity.account_count ?? 0}</TableCell>
                  <TableCell>{entity.entry_count ?? 0}</TableCell>
                  <TableCell>
                    {editingEntityId === entity.id ? (
                      <div className="table-actions">
                        <Button type="button" size="sm" disabled={isUpdating} onClick={() => onSaveEntity(entity.id)}>
                          Save
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={onCancelEditEntity}>
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <Button type="button" size="sm" variant="outline" onClick={() => onStartEditEntity(entity)}>
                        Edit
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="muted">{hasAnyEntities ? "No entities match the current search." : "No entities yet."}</p>
        )
      ) : null}

      {updateErrorMessage ? <p className="error">{updateErrorMessage}</p> : null}
    </div>
  );
}

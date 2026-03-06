import type { FormEvent } from "react";
import { Plus } from "lucide-react";

import type { Tag } from "../../../lib/types";
import { DeleteConfirmDialog } from "../../../components/DeleteConfirmDialog";
import { CreatableSingleSelect } from "../../../components/CreatableSingleSelect";
import { Button } from "../../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "../../../components/ui/dialog";
import { FormField } from "../../../components/ui/form-field";
import { Input } from "../../../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";

interface TagsSectionProps {
  search: string;
  onSearchChange: (value: string) => void;
  createPanelOpen: boolean;
  onToggleCreatePanel: () => void;
  onCloseCreatePanel: () => void;
  newTagName: string;
  onNewTagNameChange: (value: string) => void;
  newTagType: string;
  onNewTagTypeChange: (value: string) => void;
  newTagColor: string;
  onNewTagColorChange: (value: string) => void;
  newTagDescription: string;
  onNewTagDescriptionChange: (value: string) => void;
  editingTagId: number | null;
  editingTagName: string;
  onEditingTagNameChange: (value: string) => void;
  editingTagType: string;
  onEditingTagTypeChange: (value: string) => void;
  editingTagColor: string;
  onEditingTagColorChange: (value: string) => void;
  editingTagDescription: string;
  onEditingTagDescriptionChange: (value: string) => void;
  onStartEditTag: (tag: Tag) => void;
  onCancelEditTag: () => void;
  onSaveTag: (tagId: number) => void;
  onStartDeleteTag: (tag: Tag) => void;
  onCancelDeleteTag: () => void;
  onConfirmDeleteTag: () => void;
  onCreateTagSubmit: (event: FormEvent<HTMLFormElement>) => void;
  tags: Tag[] | undefined;
  deletingTag: Tag | null;
  hasAnyTags: boolean;
  tagTypeOptions: string[];
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

export function TagsSection(props: TagsSectionProps) {
  const {
    search,
    onSearchChange,
    createPanelOpen,
    onToggleCreatePanel,
    onCloseCreatePanel,
    newTagName,
    onNewTagNameChange,
    newTagType,
    onNewTagTypeChange,
    newTagColor,
    onNewTagColorChange,
    newTagDescription,
    onNewTagDescriptionChange,
    editingTagId,
    editingTagName,
    onEditingTagNameChange,
    editingTagType,
    onEditingTagTypeChange,
    editingTagColor,
    onEditingTagColorChange,
    editingTagDescription,
    onEditingTagDescriptionChange,
    onStartEditTag,
    onCancelEditTag,
    onSaveTag,
    onStartDeleteTag,
    onCancelDeleteTag,
    onConfirmDeleteTag,
    onCreateTagSubmit,
    tags,
    deletingTag,
    hasAnyTags,
    tagTypeOptions,
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

  return (
    <div className="table-shell">
      <div className="table-shell-header">
        <div>
          <h3 className="table-shell-title">Tags</h3>
          <p className="table-shell-subtitle">Manage tags, colors, and taxonomy-backed types.</p>
        </div>
      </div>
      <div className="table-toolbar">
        <div className="table-toolbar-filters">
          <label className="field min-w-[220px] grow">
            <span>Search</span>
            <Input
              placeholder="Filter by tag, type, or description"
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
            />
          </label>
        </div>
        <div className="table-toolbar-action">
          <Button type="button" size="icon" variant="outline" aria-label="Add tag" onClick={onToggleCreatePanel}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isLoading ? <p>Loading tags...</p> : null}
      {isError ? <p className="error">{queryErrorMessage}</p> : null}

      {tags ? (
        tags.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tags.map((tag) => (
                <TableRow key={tag.id}>
                  <TableCell>
                    <span className="tag-color-cell">
                      <span className="tag-color-dot" style={{ backgroundColor: tag.color || "hsl(var(--muted))" }} />
                      {tag.name}
                    </span>
                  </TableCell>
                  <TableCell>{tag.type || "(none)"}</TableCell>
                  <TableCell>{tag.description || "(none)"}</TableCell>
                  <TableCell>
                    <div className="table-actions">
                      <Button type="button" size="sm" variant="outline" onClick={() => onStartEditTag(tag)}>
                        Edit
                      </Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => onStartDeleteTag(tag)}>
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="muted">{hasAnyTags ? "No tags match the current search." : "No tags yet."}</p>
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
              <DialogTitle>Create Tag</DialogTitle>
            <DialogDescription>Add a tag with optional taxonomy type and color token.</DialogDescription>
            </DialogHeader>
          <form className="grid gap-4" onSubmit={onCreateTagSubmit}>
            <FormField label="Name">
              <Input placeholder="e.g. groceries" value={newTagName} onChange={(event) => onNewTagNameChange(event.target.value)} />
            </FormField>
            <FormField label="Type">
              <CreatableSingleSelect
                value={newTagType}
                options={tagTypeOptions}
                ariaLabel="Tag type"
                placeholder="Select or create type..."
                onChange={onNewTagTypeChange}
              />
            </FormField>
            <FormField label="Color">
              <Input placeholder="e.g. #7fb069" value={newTagColor} onChange={(event) => onNewTagColorChange(event.target.value)} />
            </FormField>
            <FormField label="Description">
              <Input
                placeholder="e.g. Regular household grocery expenses"
                value={newTagDescription}
                onChange={(event) => onNewTagDescriptionChange(event.target.value)}
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
        open={editingTagId !== null}
        onOpenChange={(open) => {
          if (!open) {
            onCancelEditTag();
          }
        }}
      >
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Edit Tag</DialogTitle>
            <DialogDescription>Update tag naming, type, and display color.</DialogDescription>
          </DialogHeader>
          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (editingTagId === null) {
                return;
              }
              onSaveTag(editingTagId);
            }}
          >
            <FormField label="Name">
              <Input
                placeholder="e.g. groceries"
                value={editingTagName}
                onChange={(event) => onEditingTagNameChange(event.target.value)}
              />
            </FormField>
            <FormField label="Type">
              <CreatableSingleSelect
                value={editingTagType}
                options={tagTypeOptions}
                ariaLabel="Edit tag type"
                placeholder="Select or create type..."
                onChange={onEditingTagTypeChange}
              />
            </FormField>
            <FormField label="Color">
              <Input placeholder="e.g. #7fb069" value={editingTagColor} onChange={(event) => onEditingTagColorChange(event.target.value)} />
            </FormField>
            <FormField label="Description">
              <Input
                placeholder="e.g. Regular household grocery expenses"
                value={editingTagDescription}
                onChange={(event) => onEditingTagDescriptionChange(event.target.value)}
              />
            </FormField>
            {updateErrorMessage ? <p className="error">{updateErrorMessage}</p> : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onCancelEditTag}>
                Cancel
              </Button>
              <Button type="submit" disabled={isUpdating || editingTagId === null}>
                {isUpdating ? "Saving..." : "Save"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <DeleteConfirmDialog
        open={deletingTag !== null}
        onOpenChange={(open) => {
          if (!open) {
            onCancelDeleteTag();
          }
        }}
        title={deletingTag ? `Delete ${deletingTag.name}?` : "Delete tag?"}
        description="This removes the tag record and detaches it from any entries that still reference it."
        confirmLabel="Delete tag"
        isPending={isDeleting}
        errorMessage={deleteErrorMessage}
        warnings={
          deletingTag && (deletingTag.entry_count ?? 0) > 0
            ? ["Entries keep their ledger history, but this tag will be removed from those entries."]
            : []
        }
        onConfirm={onConfirmDeleteTag}
      />
    </div>
  );
}

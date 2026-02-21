import type { FormEvent } from "react";
import { Plus } from "lucide-react";

import type { Tag } from "../../../lib/types";
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
  newTagCategory: string;
  onNewTagCategoryChange: (value: string) => void;
  newTagColor: string;
  onNewTagColorChange: (value: string) => void;
  editingTagId: number | null;
  editingTagName: string;
  onEditingTagNameChange: (value: string) => void;
  editingTagCategory: string;
  onEditingTagCategoryChange: (value: string) => void;
  editingTagColor: string;
  onEditingTagColorChange: (value: string) => void;
  onStartEditTag: (tag: Tag) => void;
  onCancelEditTag: () => void;
  onSaveTag: (tagId: number) => void;
  onCreateTagSubmit: (event: FormEvent<HTMLFormElement>) => void;
  tags: Tag[] | undefined;
  hasAnyTags: boolean;
  tagCategoryOptions: string[];
  isLoading: boolean;
  isError: boolean;
  queryErrorMessage: string | null;
  createErrorMessage: string | null;
  updateErrorMessage: string | null;
  isCreating: boolean;
  isUpdating: boolean;
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
    newTagCategory,
    onNewTagCategoryChange,
    newTagColor,
    onNewTagColorChange,
    editingTagId,
    editingTagName,
    onEditingTagNameChange,
    editingTagCategory,
    onEditingTagCategoryChange,
    editingTagColor,
    onEditingTagColorChange,
    onStartEditTag,
    onCancelEditTag,
    onSaveTag,
    onCreateTagSubmit,
    tags,
    hasAnyTags,
    tagCategoryOptions,
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
          <h3 className="table-shell-title">Tags</h3>
          <p className="table-shell-subtitle">Manage tags, colors, and taxonomy-backed categories.</p>
        </div>
      </div>
      <div className="table-toolbar">
        <div className="table-toolbar-filters">
          <label className="field min-w-[220px] grow">
            <span>Search</span>
            <Input
              placeholder="Filter by tag, category, or color"
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
                <TableHead>Category</TableHead>
                <TableHead>Color</TableHead>
                <TableHead>Entries</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tags.map((tag) => (
                <TableRow key={tag.id}>
                  <TableCell>{tag.name}</TableCell>
                  <TableCell>{tag.category || "(none)"}</TableCell>
                  <TableCell>
                    <span className="tag-color-cell">
                      <span className="tag-color-dot" style={{ backgroundColor: tag.color || "hsl(var(--muted))" }} />
                      {tag.color || "(none)"}
                    </span>
                  </TableCell>
                  <TableCell>{tag.entry_count ?? 0}</TableCell>
                  <TableCell>
                    <Button type="button" size="sm" variant="outline" onClick={() => onStartEditTag(tag)}>
                      Edit
                    </Button>
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
            <DialogDescription>Add a tag with optional taxonomy category and color token.</DialogDescription>
          </DialogHeader>
          <form className="grid gap-4" onSubmit={onCreateTagSubmit}>
            <FormField label="Name">
              <Input placeholder="e.g. groceries" value={newTagName} onChange={(event) => onNewTagNameChange(event.target.value)} />
            </FormField>
            <FormField label="Category">
              <CreatableSingleSelect
                value={newTagCategory}
                options={tagCategoryOptions}
                ariaLabel="Tag category"
                placeholder="Select or create category..."
                onChange={onNewTagCategoryChange}
              />
            </FormField>
            <FormField label="Color">
              <Input placeholder="e.g. #7fb069" value={newTagColor} onChange={(event) => onNewTagColorChange(event.target.value)} />
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
            <DialogDescription>Update tag naming, category, and display color.</DialogDescription>
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
            <FormField label="Category">
              <CreatableSingleSelect
                value={editingTagCategory}
                options={tagCategoryOptions}
                ariaLabel="Edit tag category"
                placeholder="Select or create category..."
                onChange={onEditingTagCategoryChange}
              />
            </FormField>
            <FormField label="Color">
              <Input placeholder="e.g. #7fb069" value={editingTagColor} onChange={(event) => onEditingTagColorChange(event.target.value)} />
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
    </div>
  );
}

import type { FormEvent } from "react";
import { Plus } from "lucide-react";

import type { Tag } from "../../../lib/types";
import { CreatableSingleSelect } from "../../../components/CreatableSingleSelect";
import { Button } from "../../../components/ui/button";
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
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label={createPanelOpen ? "Cancel add tag" : "Add tag"}
            onClick={onToggleCreatePanel}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {createPanelOpen ? (
        <form className="table-inline-form" onSubmit={onCreateTagSubmit}>
          <label className="field min-w-[200px] grow">
            <span>Name</span>
            <Input placeholder="e.g. groceries" value={newTagName} onChange={(event) => onNewTagNameChange(event.target.value)} />
          </label>
          <label className="field min-w-[220px] grow">
            <span>Category</span>
            <CreatableSingleSelect
              value={newTagCategory}
              options={tagCategoryOptions}
              ariaLabel="Tag category"
              placeholder="Select or create category..."
              onChange={onNewTagCategoryChange}
            />
          </label>
          <label className="field min-w-[180px]">
            <span>Color</span>
            <Input placeholder="e.g. #7fb069" value={newTagColor} onChange={(event) => onNewTagColorChange(event.target.value)} />
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
                  <TableCell>
                    {editingTagId === tag.id ? (
                      <Input value={editingTagName} className="h-8" onChange={(event) => onEditingTagNameChange(event.target.value)} />
                    ) : (
                      tag.name
                    )}
                  </TableCell>
                  <TableCell>
                    {editingTagId === tag.id ? (
                      <div className="min-w-[200px]">
                        <CreatableSingleSelect
                          value={editingTagCategory}
                          options={tagCategoryOptions}
                          ariaLabel="Edit tag category"
                          placeholder="Select or create category..."
                          onChange={onEditingTagCategoryChange}
                        />
                      </div>
                    ) : (
                      tag.category || "(none)"
                    )}
                  </TableCell>
                  <TableCell>
                    {editingTagId === tag.id ? (
                      <Input value={editingTagColor} className="h-8" onChange={(event) => onEditingTagColorChange(event.target.value)} />
                    ) : (
                      <span className="tag-color-cell">
                        <span className="tag-color-dot" style={{ backgroundColor: tag.color || "hsl(var(--muted))" }} />
                        {tag.color || "(none)"}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>{tag.entry_count ?? 0}</TableCell>
                  <TableCell>
                    {editingTagId === tag.id ? (
                      <div className="table-actions">
                        <Button type="button" size="sm" disabled={isUpdating} onClick={() => onSaveTag(tag.id)}>
                          Save
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={onCancelEditTag}>
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <Button type="button" size="sm" variant="outline" onClick={() => onStartEditTag(tag)}>
                        Edit
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="muted">{hasAnyTags ? "No tags match the current search." : "No tags yet."}</p>
        )
      ) : null}

      {updateErrorMessage ? <p className="error">{updateErrorMessage}</p> : null}
    </div>
  );
}

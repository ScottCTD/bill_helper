import type { FormEvent } from "react";
import { Plus } from "lucide-react";

import type { TaxonomyTerm } from "../../../lib/types";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";

interface TaxonomyTermsSectionProps {
  label: string;
  search: string;
  onSearchChange: (value: string) => void;
  createPanelOpen: boolean;
  onToggleCreatePanel: () => void;
  onCloseCreatePanel: () => void;
  newTermName: string;
  onNewTermNameChange: (value: string) => void;
  editingTermId: string;
  editingTermName: string;
  onEditingTermNameChange: (value: string) => void;
  onStartEditTerm: (term: TaxonomyTerm) => void;
  onCancelEditTerm: () => void;
  onSaveTerm: (termId: string) => void;
  onCreateTermSubmit: (event: FormEvent<HTMLFormElement>) => void;
  terms: TaxonomyTerm[] | undefined;
  hasAnyTerms: boolean;
  isLoading: boolean;
  isError: boolean;
  queryErrorMessage: string | null;
  createErrorMessage: string | null;
  updateErrorMessage: string | null;
  isCreating: boolean;
  isUpdating: boolean;
}

export function TaxonomyTermsSection(props: TaxonomyTermsSectionProps) {
  const {
    label,
    search,
    onSearchChange,
    createPanelOpen,
    onToggleCreatePanel,
    onCloseCreatePanel,
    newTermName,
    onNewTermNameChange,
    editingTermId,
    editingTermName,
    onEditingTermNameChange,
    onStartEditTerm,
    onCancelEditTerm,
    onSaveTerm,
    onCreateTermSubmit,
    terms,
    hasAnyTerms,
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
          <h3 className="table-shell-title">{label}</h3>
          <p className="table-shell-subtitle">Flat taxonomy terms used by this catalog. Usage equals assigned records.</p>
        </div>
      </div>
      <div className="table-toolbar">
        <div className="table-toolbar-filters">
          <label className="field min-w-[220px] grow">
            <span>Search</span>
            <Input placeholder="Filter categories" value={search} onChange={(event) => onSearchChange(event.target.value)} />
          </label>
        </div>
        <div className="table-toolbar-action">
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label={createPanelOpen ? "Cancel add category" : "Add category"}
            onClick={onToggleCreatePanel}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {createPanelOpen ? (
        <form className="table-inline-form" onSubmit={onCreateTermSubmit}>
          <label className="field min-w-[220px] grow">
            <span>Name</span>
            <Input placeholder="e.g. food" value={newTermName} onChange={(event) => onNewTermNameChange(event.target.value)} />
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
      {isLoading ? <p>Loading categories...</p> : null}
      {isError ? <p className="error">{queryErrorMessage}</p> : null}

      {terms ? (
        terms.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Usage</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {terms.map((term) => (
                <TableRow key={term.id}>
                  <TableCell>
                    {editingTermId === term.id ? (
                      <Input value={editingTermName} className="h-8" onChange={(event) => onEditingTermNameChange(event.target.value)} />
                    ) : (
                      term.name
                    )}
                  </TableCell>
                  <TableCell>{term.usage_count}</TableCell>
                  <TableCell>
                    {editingTermId === term.id ? (
                      <div className="table-actions">
                        <Button type="button" size="sm" disabled={isUpdating} onClick={() => onSaveTerm(term.id)}>
                          Save
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={onCancelEditTerm}>
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <Button type="button" size="sm" variant="outline" onClick={() => onStartEditTerm(term)}>
                        Rename
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="muted">{hasAnyTerms ? "No categories match the current search." : "No categories yet."}</p>
        )
      ) : null}

      {updateErrorMessage ? <p className="error">{updateErrorMessage}</p> : null}
    </div>
  );
}

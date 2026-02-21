import { useEffect, useMemo, useState } from "react";

import type { LinkType } from "../lib/types";
import { SingleSelect } from "./SingleSelect";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";
import { Input } from "./ui/input";
import { NativeSelect } from "./ui/native-select";

const LINK_TYPE_OPTIONS: LinkType[] = ["RECURRING", "SPLIT", "BUNDLE"];

export interface LinkEditorOption {
  id: string;
  label: string;
}

interface LinkEditorSubmitPayload {
  source_entry_id: string;
  target_entry_id: string;
  link_type: LinkType;
  note?: string;
}

interface LinkEditorModalProps {
  isOpen: boolean;
  title: string;
  description: string;
  entryOptions: LinkEditorOption[];
  fixedSourceEntryId?: string;
  fixedSourceLabel?: string;
  entryOptionsLoading?: boolean;
  entryOptionsError?: string | null;
  entryOptionsNotice?: string | null;
  isSaving: boolean;
  saveError?: string | null;
  onClose: () => void;
  onSubmit: (payload: LinkEditorSubmitPayload) => void;
}

export function LinkEditorModal({
  isOpen,
  title,
  description,
  entryOptions,
  fixedSourceEntryId,
  fixedSourceLabel,
  entryOptionsLoading = false,
  entryOptionsError = null,
  entryOptionsNotice = null,
  isSaving,
  saveError = null,
  onClose,
  onSubmit
}: LinkEditorModalProps) {
  const [formError, setFormError] = useState<string | null>(null);
  const [draft, setDraft] = useState({
    source_entry_id: fixedSourceEntryId ?? "",
    target_entry_id: "",
    link_type: "BUNDLE" as LinkType,
    note: ""
  });

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setFormError(null);
    setDraft({
      source_entry_id: fixedSourceEntryId ?? "",
      target_entry_id: "",
      link_type: "BUNDLE",
      note: ""
    });
  }, [fixedSourceEntryId, isOpen]);

  const sourceOptions = useMemo(() => {
    if (fixedSourceEntryId) {
      return entryOptions.filter((option) => option.id !== fixedSourceEntryId);
    }
    return entryOptions;
  }, [entryOptions, fixedSourceEntryId]);

  const targetOptions = useMemo(() => {
    return entryOptions.filter((option) => option.id !== draft.source_entry_id);
  }, [draft.source_entry_id, entryOptions]);

  const sourceSelectOptions = useMemo(
    () =>
      sourceOptions.map((option) => ({
        value: option.id,
        label: option.label
      })),
    [sourceOptions]
  );

  const targetSelectOptions = useMemo(
    () =>
      targetOptions.map((option) => ({
        value: option.id,
        label: option.label
      })),
    [targetOptions]
  );

  function submit() {
    setFormError(null);

    if (entryOptionsLoading || entryOptionsError) {
      setFormError("Entry options are unavailable.");
      return;
    }

    if (!draft.source_entry_id || !draft.target_entry_id) {
      setFormError("Select both source and target entries.");
      return;
    }

    if (draft.source_entry_id === draft.target_entry_id) {
      setFormError("Source and target entries must be different.");
      return;
    }

    onSubmit({
      source_entry_id: draft.source_entry_id,
      target_entry_id: draft.target_entry_id,
      link_type: draft.link_type,
      note: draft.note.trim() ? draft.note.trim() : undefined
    });
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="stack-sm">
          {fixedSourceEntryId ? (
            <label className="field min-w-0">
              <span>Source entry</span>
              <Input disabled value={fixedSourceLabel ?? fixedSourceEntryId} />
            </label>
          ) : (
            <label className="field min-w-0">
              <span>Source entry</span>
              <SingleSelect
                value={draft.source_entry_id}
                options={sourceSelectOptions}
                placeholder="Select source..."
                disabled={entryOptionsLoading || Boolean(entryOptionsError)}
                searchable
                searchPlaceholder="Search source entry..."
                onChange={(nextSourceEntryId) =>
                  setDraft((current) => ({
                    ...current,
                    source_entry_id: nextSourceEntryId,
                    target_entry_id: current.target_entry_id === nextSourceEntryId ? "" : current.target_entry_id
                  }))
                }
              />
            </label>
          )}

          <label className="field min-w-0">
            <span>Target entry</span>
            <SingleSelect
              value={draft.target_entry_id}
              options={targetSelectOptions}
              placeholder="Select target..."
              disabled={entryOptionsLoading || Boolean(entryOptionsError)}
              searchable
              searchPlaceholder="Search target entry..."
              onChange={(nextTargetEntryId) => setDraft((current) => ({ ...current, target_entry_id: nextTargetEntryId }))}
            />
          </label>

          <label className="field min-w-0">
            <span>Link type</span>
            <NativeSelect value={draft.link_type} onChange={(event) => setDraft((current) => ({ ...current, link_type: event.target.value as LinkType }))}>
              {LINK_TYPE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </NativeSelect>
          </label>

          <label className="field min-w-0">
            <span>Note (optional)</span>
            <Input
              value={draft.note}
              onChange={(event) => setDraft((current) => ({ ...current, note: event.target.value }))}
              placeholder="Describe why this relationship exists"
            />
          </label>

          {entryOptionsLoading ? <p className="muted">Loading entries...</p> : null}
          {entryOptionsNotice ? <p className="muted">{entryOptionsNotice}</p> : null}
          {entryOptionsError ? <p className="error">{entryOptionsError}</p> : null}
          {formError ? <p className="error">{formError}</p> : null}
          {saveError ? <p className="error">{saveError}</p> : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button type="button" onClick={submit} disabled={isSaving}>
            {isSaving ? "Saving..." : "Create link"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

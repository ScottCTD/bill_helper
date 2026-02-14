import { FormEvent, useEffect, useMemo, useState } from "react";

import type { Currency, Entity, Entry, EntryKind, Tag, User } from "../lib/types";
import { CreatableSingleSelect } from "./CreatableSingleSelect";
import { MarkdownBlockEditor } from "./MarkdownBlockEditor";
import { SingleSelect } from "./SingleSelect";
import { TagMultiSelect } from "./TagMultiSelect";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";
import { Input } from "./ui/input";
import { NativeSelect } from "./ui/native-select";

interface EntryEditorFormState {
  kind: EntryKind;
  occurred_at: string;
  name: string;
  amount_major: string;
  currency_code: string;
  from_entity_value: string;
  to_entity_value: string;
  owner_user_id: string;
  tags: string[];
  markdown_body: string;
}

export interface EntryEditorSubmitPayload {
  kind: EntryKind;
  occurred_at: string;
  name: string;
  amount_minor: number;
  currency_code: string;
  from_entity_id: string | null;
  from_entity: string | null;
  to_entity_id: string | null;
  to_entity: string | null;
  owner_user_id: string | null;
  tags: string[];
  markdown_body: string | null;
}

interface EntryEditorModalProps {
  isOpen: boolean;
  mode: "create" | "edit";
  entry: Entry | null;
  currencies: Currency[];
  entities: Entity[];
  users: User[];
  tags: Tag[];
  currentUserId: string;
  defaultCurrencyCode: string;
  isSaving: boolean;
  loadError?: string | null;
  saveError?: string | null;
  onClose: () => void;
  onSubmit: (payload: EntryEditorSubmitPayload) => void;
}

const KIND_OPTIONS: Array<{ value: EntryKind; label: string }> = [
  { value: "INCOME", label: "+ Income" },
  { value: "EXPENSE", label: "- Expense" }
];

function todayDateInputValue() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function buildCreateForm(currentUserId: string, defaultCurrencyCode: string): EntryEditorFormState {
  return {
    kind: "EXPENSE",
    occurred_at: todayDateInputValue(),
    name: "",
    amount_major: "",
    currency_code: defaultCurrencyCode,
    from_entity_value: "",
    to_entity_value: "",
    owner_user_id: currentUserId,
    tags: [],
    markdown_body: ""
  };
}

function buildEditForm(entry: Entry, currentUserId: string): EntryEditorFormState {
  return {
    kind: entry.kind,
    occurred_at: entry.occurred_at,
    name: entry.name,
    amount_major: `${(entry.amount_minor / 100).toFixed(2)}`,
    currency_code: entry.currency_code,
    from_entity_value: entry.from_entity ?? "",
    to_entity_value: entry.to_entity ?? "",
    owner_user_id: entry.owner_user_id ?? currentUserId,
    tags: entry.tags.map((tag) => tag.name),
    markdown_body: entry.markdown_body ?? ""
  };
}

function normalizeTagValues(values: string[]) {
  return Array.from(
    new Set(
      values
        .map((value) => value.trim().toLowerCase())
        .filter((value) => value.length > 0)
        .sort((left, right) => left.localeCompare(right))
    )
  );
}

function normalizeAmountForDiff(value: string) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value.trim();
  }
  return parsed.toFixed(2);
}

function normalizeFormStateForDiff(state: EntryEditorFormState) {
  return {
    kind: state.kind,
    occurred_at: state.occurred_at,
    name: state.name.trim(),
    amount_major: normalizeAmountForDiff(state.amount_major),
    currency_code: state.currency_code.trim().toUpperCase(),
    from_entity_value: state.from_entity_value.trim(),
    to_entity_value: state.to_entity_value.trim(),
    owner_user_id: state.owner_user_id,
    tags: normalizeTagValues(state.tags),
    markdown_body: state.markdown_body.trim()
  };
}

function normalizeEntityValue(value: string) {
  return value.trim().toLowerCase();
}

function uniqueNormalizedEntityNames(values: string[]) {
  const uniqueValues: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const trimmed = value.trim();
    const normalized = normalizeEntityValue(trimmed);
    if (!trimmed || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    uniqueValues.push(trimmed);
  }
  return uniqueValues.sort((left, right) => left.localeCompare(right));
}

function resolveEntityInput(rawValue: string, entities: Entity[]) {
  const trimmed = rawValue.trim();
  if (!trimmed) {
    return { entityId: null, entityName: null };
  }

  const normalized = normalizeEntityValue(trimmed);
  const matchedEntity = entities.find((entity) => normalizeEntityValue(entity.name) === normalized);
  if (matchedEntity) {
    return { entityId: matchedEntity.id, entityName: null };
  }

  return { entityId: null, entityName: trimmed };
}

function areFormStatesEqual(left: EntryEditorFormState, right: EntryEditorFormState) {
  return JSON.stringify(normalizeFormStateForDiff(left)) === JSON.stringify(normalizeFormStateForDiff(right));
}

export function EntryEditorModal({
  isOpen,
  mode,
  entry,
  currencies,
  entities,
  users,
  tags,
  currentUserId,
  defaultCurrencyCode,
  isSaving,
  loadError,
  saveError,
  onClose,
  onSubmit
}: EntryEditorModalProps) {
  const [validationError, setValidationError] = useState<string | null>(null);
  const [formState, setFormState] = useState<EntryEditorFormState>(() => buildCreateForm(currentUserId, defaultCurrencyCode));
  const [initialFormState, setInitialFormState] = useState<EntryEditorFormState>(() =>
    buildCreateForm(currentUserId, defaultCurrencyCode)
  );
  const [editorResetNonce, setEditorResetNonce] = useState(0);
  const [createdEntityOptionNames, setCreatedEntityOptionNames] = useState<string[]>([]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    if (mode === "create") {
      const nextState = buildCreateForm(currentUserId, defaultCurrencyCode);
      setFormState(nextState);
      setInitialFormState(nextState);
      setValidationError(null);
      setEditorResetNonce((value) => value + 1);
      setCreatedEntityOptionNames([]);
      return;
    }

    if (entry) {
      const nextState = buildEditForm(entry, currentUserId);
      setFormState(nextState);
      setInitialFormState(nextState);
      setValidationError(null);
      setEditorResetNonce((value) => value + 1);
      setCreatedEntityOptionNames([]);
    }
  }, [currentUserId, defaultCurrencyCode, entry, isOpen, mode]);

  useEffect(() => {
    if (!isOpen || mode !== "create" || !currentUserId) {
      return;
    }

    setFormState((state) => (state.owner_user_id ? state : { ...state, owner_user_id: currentUserId }));
    setInitialFormState((state) => (state.owner_user_id ? state : { ...state, owner_user_id: currentUserId }));
  }, [currentUserId, isOpen, mode]);

  const editorResetKey = useMemo(() => {
    const scope = mode === "edit" && entry ? `${entry.id}:${entry.updated_at}` : `new:${currentUserId}`;
    return `${scope}:${editorResetNonce}`;
  }, [currentUserId, editorResetNonce, entry, mode]);

  const currencyOptions = useMemo(() => {
    const codes = new Set(currencies.map((currency) => currency.code));
    if (formState.currency_code) {
      codes.add(formState.currency_code.toUpperCase());
    }
    return Array.from(codes).sort();
  }, [currencies, formState.currency_code]);
  const entityOptionNames = useMemo(
    () => uniqueNormalizedEntityNames([...(entities.map((entity) => entity.name) ?? []), ...createdEntityOptionNames]),
    [createdEntityOptionNames, entities]
  );

  const isDirty = useMemo(() => !areFormStatesEqual(formState, initialFormState), [formState, initialFormState]);

  if (!isOpen) {
    return null;
  }

  function buildSubmitPayload(): EntryEditorSubmitPayload | null {
    const amountMinor = Math.round(Number(formState.amount_major) * 100);
    const trimmedName = formState.name.trim();
    const fromEntityResolution = resolveEntityInput(formState.from_entity_value, entities);
    const toEntityResolution = resolveEntityInput(formState.to_entity_value, entities);

    if (!trimmedName) {
      setValidationError("Name is required.");
      return null;
    }
    if (!Number.isFinite(amountMinor) || amountMinor <= 0) {
      setValidationError("Amount must be greater than 0.");
      return null;
    }
    if (!formState.occurred_at) {
      setValidationError("Date is required.");
      return null;
    }

    setValidationError(null);
    return {
      kind: formState.kind,
      occurred_at: formState.occurred_at,
      name: trimmedName,
      amount_minor: amountMinor,
      currency_code: formState.currency_code.toUpperCase(),
      from_entity_id: fromEntityResolution.entityId,
      from_entity: fromEntityResolution.entityName,
      to_entity_id: toEntityResolution.entityId,
      to_entity: toEntityResolution.entityName,
      owner_user_id: formState.owner_user_id || null,
      tags: formState.tags,
      markdown_body: formState.markdown_body.trim().length > 0 ? formState.markdown_body : null
    };
  }

  function submitCurrentForm() {
    const payload = buildSubmitPayload();
    if (!payload) {
      return false;
    }
    onSubmit(payload);
    return true;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitCurrentForm();
  }

  function handleCloseRequest() {
    if (isSaving) {
      return;
    }

    if (!isDirty || (mode === "edit" && !entry && !loadError)) {
      setValidationError(null);
      onClose();
      return;
    }

    submitCurrentForm();
  }

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) {
          handleCloseRequest();
        }
      }}
    >
      <DialogContent
        className="entry-editor-sheet h-[90vh] max-h-[90vh] overflow-y-auto"
        onInteractOutside={(event) => {
          if (isSaving) {
            event.preventDefault();
          }
        }}
        onEscapeKeyDown={(event) => {
          if (isSaving) {
            event.preventDefault();
          }
        }}
      >
        <DialogHeader className="entry-editor-header">
          <DialogTitle>{mode === "create" ? "New Entry" : "Edit Entry"}</DialogTitle>
          <DialogDescription>Close the popup to auto-save changes.</DialogDescription>
        </DialogHeader>

        {mode === "edit" && !entry && !loadError ? <p>Loading entry...</p> : null}
        {loadError ? <p className="error">{loadError}</p> : null}

        {(mode === "create" || entry) && !loadError ? (
          <form id="entry-editor-form" className="entry-editor-page" onSubmit={handleSubmit}>
            <div className="entry-property-line">
              <span className="entry-property-label">Date:</span>
              <Input
                type="date"
                className="entry-property-input"
                aria-label="Date"
                required
                value={formState.occurred_at}
                disabled={isSaving}
                onChange={(event) => setFormState((state) => ({ ...state, occurred_at: event.target.value }))}
              />
            </div>

            <div className="entry-property-line">
              <span className="entry-property-label">Name:</span>
              <Input
                aria-label="Name"
                className="entry-property-input"
                required
                value={formState.name}
                disabled={isSaving}
                onChange={(event) => setFormState((state) => ({ ...state, name: event.target.value }))}
              />
            </div>

            <div className="entry-property-line entry-property-line-group">
              <span className="entry-property-label">Kind:</span>
              <div className="entry-property-group entry-property-group-kind">
                <SingleSelect
                  value={formState.kind}
                  options={KIND_OPTIONS}
                  ariaLabel="Kind"
                  disabled={isSaving}
                  onChange={(nextKind) => setFormState((state) => ({ ...state, kind: nextKind as EntryKind }))}
                />
                <span className="entry-property-inline-label">Amount:</span>
                <Input
                  type="number"
                  aria-label="Amount"
                  className="entry-property-input-sm"
                  min="0"
                  step="0.01"
                  required
                  value={formState.amount_major}
                  disabled={isSaving}
                  onChange={(event) => setFormState((state) => ({ ...state, amount_major: event.target.value }))}
                />
                <span className="entry-property-inline-label">Currency:</span>
                <NativeSelect
                  aria-label="Currency"
                  wrapperClassName="entry-property-input-xs"
                  value={formState.currency_code}
                  disabled={isSaving}
                  onChange={(event) => setFormState((state) => ({ ...state, currency_code: event.target.value }))}
                >
                  {currencyOptions.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </NativeSelect>
              </div>
            </div>

            <div className="entry-property-line entry-property-line-group">
              <span className="entry-property-label">From:</span>
              <div className="entry-property-group entry-property-group-from-to">
                <CreatableSingleSelect
                  ariaLabel="From"
                  options={entityOptionNames}
                  placeholder="Select or create entity..."
                  createLabelPrefix="Create entity"
                  value={formState.from_entity_value}
                  disabled={isSaving}
                  onCreateOption={(createdValue) =>
                    setCreatedEntityOptionNames((current) => uniqueNormalizedEntityNames([...current, createdValue]))
                  }
                  onChange={(nextValue) => setFormState((state) => ({ ...state, from_entity_value: nextValue }))}
                />
                <span className="entry-property-inline-label">To:</span>
                <CreatableSingleSelect
                  ariaLabel="To"
                  options={entityOptionNames}
                  placeholder="Select or create entity..."
                  createLabelPrefix="Create entity"
                  value={formState.to_entity_value}
                  disabled={isSaving}
                  onCreateOption={(createdValue) =>
                    setCreatedEntityOptionNames((current) => uniqueNormalizedEntityNames([...current, createdValue]))
                  }
                  onChange={(nextValue) => setFormState((state) => ({ ...state, to_entity_value: nextValue }))}
                />
              </div>
            </div>

            <div className="entry-property-line entry-property-line-tags">
              <span className="entry-property-label">Tags:</span>
              <TagMultiSelect
                options={tags}
                value={formState.tags}
                ariaLabel="Tags"
                placeholder="Select or create tags..."
                createLabelPrefix="Create tag"
                disabled={isSaving}
                onChange={(nextTags) => setFormState((state) => ({ ...state, tags: nextTags }))}
              />
            </div>

            <div className="entry-property-line entry-property-line-group">
              <span className="entry-property-label">Owner:</span>
              <div className="entry-property-group entry-property-group-owner">
                <NativeSelect
                  aria-label="Owner"
                  wrapperClassName="entry-property-input-owner"
                  className="entry-property-input"
                  value={formState.owner_user_id}
                  disabled={isSaving}
                  onChange={(event) => setFormState((state) => ({ ...state, owner_user_id: event.target.value }))}
                >
                  <option value="">(none)</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.name}
                      {user.is_current_user ? " (Current User)" : ""}
                    </option>
                  ))}
                </NativeSelect>
              </div>
            </div>

            <section className="entry-editor-markdown">
              <MarkdownBlockEditor
                markdown={formState.markdown_body}
                resetKey={editorResetKey}
                disabled={isSaving}
                onChange={(markdown) => setFormState((state) => ({ ...state, markdown_body: markdown }))}
              />
            </section>

            {isSaving ? <p className="muted">Saving entry...</p> : null}
            {validationError ? <p className="error">{validationError}</p> : null}
            {saveError ? <p className="error">{saveError}</p> : null}
          </form>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

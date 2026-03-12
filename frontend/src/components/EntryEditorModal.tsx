import { FormEvent, useEffect, useMemo, useState } from "react";
import { ArrowLeftRight } from "lucide-react";

import type { Currency, Entity, Entry, EntryKind, GroupMemberRole, GroupSummary, Tag } from "../lib/types";
import { CreatableSingleSelect, type CreatableSingleSelectChangeMeta } from "./CreatableSingleSelect";
import { MarkdownBlockEditor } from "./MarkdownBlockEditor";
import { SingleSelect } from "./SingleSelect";
import { TagMultiSelect } from "./TagMultiSelect";
import { Button } from "./ui/button";
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
  from_entity_selected_id: string | null;
  to_entity_selected_id: string | null;
  owner_user_id: string;
  direct_group_id: string;
  direct_group_member_role: GroupMemberRole;
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
  owner_user_id: string;
  direct_group_id: string | null;
  direct_group_member_role: GroupMemberRole | null;
  tags: string[];
  markdown_body: string | null;
}

interface EntryEditorModalProps {
  isOpen: boolean;
  mode: "create" | "edit";
  entry: Entry | null;
  currencies: Currency[];
  entities: Entity[];
  groups: GroupSummary[];
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
  { value: "EXPENSE", label: "- Expense" },
  { value: "TRANSFER", label: "~ Transfer" }
];

const SPLIT_ROLE_OPTIONS: Array<{ value: GroupMemberRole; label: string }> = [
  { value: "CHILD", label: "Child" },
  { value: "PARENT", label: "Parent" }
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
    from_entity_selected_id: null,
    to_entity_selected_id: null,
    owner_user_id: currentUserId,
    direct_group_id: "",
    direct_group_member_role: "CHILD",
    tags: [],
    markdown_body: ""
  };
}

function buildEditForm(entry: Entry): EntryEditorFormState {
  return {
    kind: entry.kind,
    occurred_at: entry.occurred_at,
    name: entry.name,
    amount_major: `${(entry.amount_minor / 100).toFixed(2)}`,
    currency_code: entry.currency_code,
    from_entity_value: entry.from_entity ?? "",
    to_entity_value: entry.to_entity ?? "",
    from_entity_selected_id: entry.from_entity_id,
    to_entity_selected_id: entry.to_entity_id,
    owner_user_id: entry.owner_user_id,
    direct_group_id: entry.direct_group?.id ?? "",
    direct_group_member_role: entry.direct_group_member_role ?? "CHILD",
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

function normalizeFormStateForDiff(
  state: EntryEditorFormState,
  options?: { includeFromSelectedId?: boolean; includeToSelectedId?: boolean }
) {
  return {
    kind: state.kind,
    occurred_at: state.occurred_at,
    name: state.name.trim(),
    amount_major: normalizeAmountForDiff(state.amount_major),
    currency_code: state.currency_code.trim().toUpperCase(),
    from_entity_value: state.from_entity_value.trim(),
    to_entity_value: state.to_entity_value.trim(),
    from_entity_selected_id: options?.includeFromSelectedId ? state.from_entity_selected_id : null,
    to_entity_selected_id: options?.includeToSelectedId ? state.to_entity_selected_id : null,
    owner_user_id: state.owner_user_id,
    direct_group_id: state.direct_group_id,
    direct_group_member_role: state.direct_group_id ? state.direct_group_member_role : null,
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

function resolveEntityInput(rawValue: string, entities: Entity[], selectedEntityId: string | null = null) {
  const trimmed = rawValue.trim();
  if (!trimmed) {
    return { entityId: null, entityName: null };
  }

  if (selectedEntityId) {
    const selectedEntity = entities.find((entity) => entity.id === selectedEntityId);
    if (selectedEntity && normalizeEntityValue(selectedEntity.name) === normalizeEntityValue(trimmed)) {
      return { entityId: selectedEntity.id, entityName: null };
    }
  }

  const normalized = normalizeEntityValue(trimmed);
  const matchedEntity = entities.find((entity) => normalizeEntityValue(entity.name) === normalized);
  if (matchedEntity) {
    return { entityId: matchedEntity.id, entityName: null };
  }

  return { entityId: null, entityName: trimmed };
}

function areFormStatesEqual(
  left: EntryEditorFormState,
  right: EntryEditorFormState,
  options?: { includeFromSelectedId?: boolean; includeToSelectedId?: boolean }
) {
  return JSON.stringify(normalizeFormStateForDiff(left, options)) === JSON.stringify(normalizeFormStateForDiff(right, options));
}

function matchingEntityId(value: string, entities: Entity[]) {
  const normalized = normalizeEntityValue(value);
  if (!normalized) {
    return null;
  }

  const matchedEntity = entities.find((entity) => normalizeEntityValue(entity.name) === normalized);
  return matchedEntity?.id ?? null;
}

function nextSelectedEntityId(
  nextValue: string,
  entities: Entity[],
  meta?: CreatableSingleSelectChangeMeta
) {
  if (meta?.source === "select") {
    return matchingEntityId(nextValue, entities);
  }
  if (meta?.source === "create" || meta?.source === "input") {
    return null;
  }
  return null;
}

export function EntryEditorModal({
  isOpen,
  mode,
  entry,
  currencies,
  entities,
  groups,
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
      const nextState = buildEditForm(entry);
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
  const groupOptions = useMemo(
    () => {
      const availableGroups = [...groups];
      if (entry?.direct_group && !availableGroups.some((group) => group.id === entry.direct_group?.id)) {
        availableGroups.push({
          id: entry.direct_group.id,
          name: entry.direct_group.name,
          group_type: entry.direct_group.group_type,
          parent_group_id: null,
          direct_member_count: 0,
          direct_entry_count: 0,
          direct_child_group_count: 0,
          descendant_entry_count: 0,
          first_occurred_at: null,
          last_occurred_at: null
        });
      }

      return [
        { value: "", label: "Ungrouped" },
        ...availableGroups
          .sort((left, right) => left.name.localeCompare(right.name))
        .map((group) => ({
          value: group.id,
          label: `${group.name} · ${group.group_type}${group.parent_group_id ? " · child group" : ""}`
        }))
      ];
    },
    [entry?.direct_group, groups]
  );
  const selectedGroupType = useMemo(
    () =>
      groups.find((group) => group.id === formState.direct_group_id)?.group_type ??
      (entry?.direct_group?.id === formState.direct_group_id ? entry.direct_group.group_type : null),
    [entry?.direct_group, formState.direct_group_id, groups]
  );

  const isDirty = useMemo(
    () =>
      !areFormStatesEqual(formState, initialFormState, {
        includeFromSelectedId: Boolean(entry?.from_entity_missing),
        includeToSelectedId: Boolean(entry?.to_entity_missing)
      }),
    [entry?.from_entity_missing, entry?.to_entity_missing, formState, initialFormState]
  );

  if (!isOpen) {
    return null;
  }

  function buildSubmitPayload(): EntryEditorSubmitPayload | null {
    const amountMinor = Math.round(Number(formState.amount_major) * 100);
    const trimmedName = formState.name.trim();
    const ownerUserId = formState.owner_user_id || currentUserId;
    const fromEntityResolution = resolveEntityInput(
      formState.from_entity_value,
      entities,
      formState.from_entity_selected_id
    );
    const toEntityResolution = resolveEntityInput(formState.to_entity_value, entities, formState.to_entity_selected_id);

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
    if (!ownerUserId) {
      setValidationError("Owner is required.");
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
      owner_user_id: ownerUserId,
      direct_group_id: formState.direct_group_id || null,
      direct_group_member_role: formState.direct_group_id ? (selectedGroupType === "SPLIT" ? formState.direct_group_member_role : null) : null,
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

  function handleSwapFromAndTo() {
    setFormState((state) => ({
      ...state,
      from_entity_value: state.to_entity_value,
      to_entity_value: state.from_entity_value,
      from_entity_selected_id: state.to_entity_selected_id,
      to_entity_selected_id: state.from_entity_selected_id
    }));
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
              <div className="grid gap-2">
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
                    onChange={(nextValue, meta) =>
                      setFormState((state) => ({
                        ...state,
                        from_entity_value: nextValue,
                        from_entity_selected_id: nextSelectedEntityId(nextValue, entities, meta)
                      }))
                    }
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="h-9 w-9 shrink-0 rounded-full"
                    aria-label="Swap from and to"
                    disabled={isSaving}
                    onClick={handleSwapFromAndTo}
                  >
                    <ArrowLeftRight className="h-4 w-4" />
                  </Button>
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
                    onChange={(nextValue, meta) =>
                      setFormState((state) => ({
                        ...state,
                        to_entity_value: nextValue,
                        to_entity_selected_id: nextSelectedEntityId(nextValue, entities, meta)
                      }))
                    }
                  />
                </div>
                {entry?.from_entity_missing || entry?.to_entity_missing ? (
                  <p className="text-xs text-muted-foreground">
                    Missing entity marker: preserved labels remain visible because the original entity no longer exists.
                  </p>
                ) : null}
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
              <span className="entry-property-label">Group:</span>
              <div className="grid gap-2">
                <div className="entry-property-group entry-property-group-group">
                  <SingleSelect
                    value={formState.direct_group_id}
                    options={groupOptions}
                    ariaLabel="Group"
                    placeholder="Ungrouped"
                    searchable
                    searchPlaceholder="Search groups..."
                    emptyLabel="No matching groups."
                    disabled={isSaving}
                    onChange={(nextValue) =>
                      setFormState((state) => ({
                        ...state,
                        direct_group_id: nextValue,
                        direct_group_member_role: nextValue ? state.direct_group_member_role : "CHILD"
                      }))
                    }
                  />
                  {selectedGroupType === "SPLIT" ? (
                    <>
                      <span className="entry-property-inline-label">Split role:</span>
                      <SingleSelect
                        value={formState.direct_group_member_role}
                        options={SPLIT_ROLE_OPTIONS}
                        ariaLabel="Split role"
                        disabled={isSaving}
                        onChange={(nextValue) =>
                          setFormState((state) => ({ ...state, direct_group_member_role: nextValue as GroupMemberRole }))
                        }
                      />
                    </>
                  ) : null}
                </div>
                <p className="text-xs text-muted-foreground">
                  Each entry can belong to one direct group. Choose a child group here if you want the parent path to be derived automatically.
                </p>
              </div>
            </div>

            <div className="entry-property-line entry-property-line-notes">
              <span className="entry-property-label">Notes:</span>
              <div className="entry-editor-markdown">
                <MarkdownBlockEditor
                  markdown={formState.markdown_body}
                  resetKey={editorResetKey}
                  disabled={isSaving}
                  onChange={(markdown) => setFormState((state) => ({ ...state, markdown_body: markdown }))}
                />
              </div>
            </div>

            {isSaving ? <p className="muted">Saving entry...</p> : null}
            {validationError ? <p className="error">{validationError}</p> : null}
            {saveError ? <p className="error">{saveError}</p> : null}
          </form>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

import { useMemo } from "react";

import { CreatableSingleSelect } from "../../../components/CreatableSingleSelect";
import { TagMultiSelect } from "../../../components/TagMultiSelect";
import { FormField } from "../../../components/ui/form-field";
import { Input } from "../../../components/ui/input";
import { NativeSelect } from "../../../components/ui/native-select";
import { Textarea } from "../../../components/ui/textarea";
import type { Currency, Entity, Tag } from "../../../lib/types";
import {
  type AccountReviewDraft,
  buildEntryReviewDraftFromPreview,
  type EntityReviewDraft,
  type EntryReviewDraft,
  type TagReviewDraft,
  uniqueEntityOptionNames
} from "./drafts";
import { collectCurrencyOptions, KIND_OPTIONS } from "./modalHelpers";

export function ReviewEntryEditor({
  draft,
  currencies,
  entities,
  tags,
  validationError,
  isDisabled,
  onDraftChange
}: {
  draft: EntryReviewDraft;
  currencies: Currency[];
  entities: Entity[];
  tags: Tag[];
  validationError: string | null;
  isDisabled: boolean;
  onDraftChange: (nextDraft: EntryReviewDraft) => void;
}) {
  const currencyOptions = useMemo(
    () => collectCurrencyOptions(currencies, draft.currencyCode),
    [currencies, draft.currencyCode]
  );
  const entityOptions = useMemo(
    () => uniqueEntityOptionNames(entities, [draft.fromEntity, draft.toEntity]),
    [draft.fromEntity, draft.toEntity, entities]
  );

  return (
    <div className="agent-review-editor-grid">
      <div className="agent-review-editor-row">
        <FormField label="Date">
          <Input
            type="date"
            value={draft.date}
            disabled={isDisabled}
            onChange={(event) => onDraftChange({ ...draft, date: event.target.value })}
          />
        </FormField>
        <FormField label="Kind">
          <NativeSelect
            value={draft.kind}
            disabled={isDisabled}
            onChange={(event) => onDraftChange({ ...draft, kind: event.target.value as EntryReviewDraft["kind"] })}
          >
            {KIND_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </NativeSelect>
        </FormField>
      </div>

      <FormField label="Name">
        <Input value={draft.name} disabled={isDisabled} onChange={(event) => onDraftChange({ ...draft, name: event.target.value })} />
      </FormField>

      <div className="agent-review-editor-row">
        <FormField label="Amount">
          <Input
            type="number"
            min="0"
            step="0.01"
            value={draft.amountMajor}
            disabled={isDisabled}
            onChange={(event) => onDraftChange({ ...draft, amountMajor: event.target.value })}
          />
        </FormField>
        <FormField label="Currency">
          <NativeSelect
            value={draft.currencyCode}
            disabled={isDisabled}
            onChange={(event) => onDraftChange({ ...draft, currencyCode: event.target.value })}
          >
            {currencyOptions.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </NativeSelect>
        </FormField>
      </div>

      <div className="agent-review-editor-row">
        <FormField label="From entity">
          <CreatableSingleSelect
            value={draft.fromEntity}
            options={entityOptions}
            disabled={isDisabled}
            ariaLabel="From entity"
            placeholder="Select or create entity..."
            onChange={(nextValue) => onDraftChange({ ...draft, fromEntity: nextValue })}
          />
        </FormField>
        <FormField label="To entity">
          <CreatableSingleSelect
            value={draft.toEntity}
            options={entityOptions}
            disabled={isDisabled}
            ariaLabel="To entity"
            placeholder="Select or create entity..."
            onChange={(nextValue) => onDraftChange({ ...draft, toEntity: nextValue })}
          />
        </FormField>
      </div>

      <FormField label="Tags">
        <TagMultiSelect
          value={draft.tags}
          options={tags}
          disabled={isDisabled}
          ariaLabel="Tags"
          onChange={(nextTags) => onDraftChange({ ...draft, tags: nextTags })}
        />
      </FormField>

      <FormField label="Notes" error={validationError}>
        <Textarea
          rows={5}
          value={draft.markdownNotes}
          disabled={isDisabled}
          onChange={(event) => onDraftChange({ ...draft, markdownNotes: event.target.value })}
        />
      </FormField>
    </div>
  );
}

export function ReviewTagEditor({
  draft,
  typeOptions,
  validationError,
  isDisabled,
  onDraftChange
}: {
  draft: TagReviewDraft;
  typeOptions: string[];
  validationError: string | null;
  isDisabled: boolean;
  onDraftChange: (nextDraft: TagReviewDraft) => void;
}) {
  return (
    <div className="agent-review-editor-grid">
      <FormField label="Name">
        <Input value={draft.name} disabled={isDisabled} onChange={(event) => onDraftChange({ ...draft, name: event.target.value })} />
      </FormField>
      <FormField label="Type" error={validationError}>
        <CreatableSingleSelect
          value={draft.type}
          options={typeOptions}
          disabled={isDisabled}
          ariaLabel="Tag type"
          placeholder="Select or create type..."
          onChange={(nextValue) => onDraftChange({ ...draft, type: nextValue })}
        />
      </FormField>
    </div>
  );
}

export function ReviewAccountEditor({
  draft,
  currencies,
  validationError,
  isDisabled,
  onDraftChange
}: {
  draft: AccountReviewDraft;
  currencies: Currency[];
  validationError: string | null;
  isDisabled: boolean;
  onDraftChange: (nextDraft: AccountReviewDraft) => void;
}) {
  const currencyOptions = useMemo(
    () => collectCurrencyOptions(currencies, draft.currencyCode),
    [currencies, draft.currencyCode]
  );
  const nameError = validationError === "Name is required." ? validationError : undefined;
  const currencyError = validationError === "Currency is required." ? validationError : undefined;

  return (
    <div className="agent-review-editor-grid">
      <FormField label="Name" error={nameError}>
        <Input value={draft.name} disabled={isDisabled} onChange={(event) => onDraftChange({ ...draft, name: event.target.value })} />
      </FormField>

      <div className="agent-review-editor-row">
        <FormField label="Currency" error={currencyError}>
          <NativeSelect
            value={draft.currencyCode}
            disabled={isDisabled}
            onChange={(event) => onDraftChange({ ...draft, currencyCode: event.target.value })}
          >
            {currencyOptions.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </NativeSelect>
        </FormField>
        <FormField label="Status">
          <NativeSelect
            value={draft.isActive ? "active" : "inactive"}
            disabled={isDisabled}
            onChange={(event) => onDraftChange({ ...draft, isActive: event.target.value === "active" })}
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </NativeSelect>
        </FormField>
      </div>

      <FormField label="Notes">
        <Textarea
          rows={5}
          value={draft.markdownBody}
          disabled={isDisabled}
          onChange={(event) => onDraftChange({ ...draft, markdownBody: event.target.value })}
        />
      </FormField>
    </div>
  );
}

export function ReviewEntityEditor({
  draft,
  categoryOptions,
  validationError,
  isDisabled,
  onDraftChange
}: {
  draft: EntityReviewDraft;
  categoryOptions: string[];
  validationError: string | null;
  isDisabled: boolean;
  onDraftChange: (nextDraft: EntityReviewDraft) => void;
}) {
  return (
    <div className="agent-review-editor-grid">
      <FormField label="Name">
        <Input value={draft.name} disabled={isDisabled} onChange={(event) => onDraftChange({ ...draft, name: event.target.value })} />
      </FormField>
      <FormField label="Category" error={validationError}>
        <CreatableSingleSelect
          value={draft.category}
          options={categoryOptions}
          disabled={isDisabled}
          ariaLabel="Entity category"
          placeholder="Select or create category..."
          onChange={(nextValue) => onDraftChange({ ...draft, category: nextValue })}
        />
      </FormField>
    </div>
  );
}

export { buildEntryReviewDraftFromPreview };

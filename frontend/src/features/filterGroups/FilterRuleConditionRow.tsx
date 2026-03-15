/**
 * CALLING SPEC:
 * - Purpose: render one editable filter-rule condition row.
 * - Inputs: callers that provide a condition, tag catalog, and change handlers.
 * - Outputs: React UI for one filter-rule condition.
 * - Side effects: React rendering and user event wiring.
 */
import { Button } from "../../components/ui/button";
import { NativeSelect } from "../../components/ui/native-select";
import { TagMultiSelect } from "../../components/TagMultiSelect";
import type { FilterRuleCondition, FilterRuleField, Tag } from "../../lib/types";
import { createConditionForField } from "./filterGroupRuleUtils";

interface FilterRuleConditionRowProps {
  condition: FilterRuleCondition;
  tags: Tag[];
  preferredTagName?: string;
  removeLabel?: string;
  disableRemove?: boolean;
  onChange: (next: FilterRuleCondition) => void;
  onRemove?: () => void;
}

export function FilterRuleConditionRow({
  condition,
  tags,
  preferredTagName,
  removeLabel = "Remove",
  disableRemove = false,
  onChange,
  onRemove
}: FilterRuleConditionRowProps) {
  return (
    <div className="rounded-xl border border-border bg-card/80 p-3">
      <div className="grid gap-3 lg:grid-cols-[180px_minmax(0,1fr)_auto] lg:items-start">
        <label className="field min-w-0">
          <span>Condition</span>
          <NativeSelect
            value={condition.field}
            onChange={(event) =>
              onChange(createConditionForField(event.target.value as FilterRuleField, condition, preferredTagName))
            }
          >
            <option value="entry_kind">Entry kind</option>
            <option value="tags">Tags</option>
            <option value="is_internal_transfer">Internal transfer</option>
          </NativeSelect>
        </label>

        {condition.field === "entry_kind" ? (
          <label className="field min-w-0">
            <span>Value</span>
            <NativeSelect value={String(condition.value)} onChange={(event) => onChange({ ...condition, value: event.target.value })}>
              <option value="EXPENSE">Expense</option>
              <option value="INCOME">Income</option>
              <option value="TRANSFER">Transfer</option>
            </NativeSelect>
          </label>
        ) : null}

        {condition.field === "tags" ? (
          <div className="grid gap-3 lg:grid-cols-[180px_minmax(0,1fr)]">
            <label className="field min-w-0">
              <span>Rule</span>
              <NativeSelect
                value={condition.operator}
                onChange={(event) =>
                  onChange({
                    ...condition,
                    operator: event.target.value as FilterRuleCondition["operator"]
                  })
                }
              >
                <option value="has_any">Includes any of</option>
                <option value="has_none">Has none of</option>
              </NativeSelect>
            </label>
            <label className="field min-w-0">
              <span>Tags</span>
              <TagMultiSelect
                options={tags}
                value={Array.isArray(condition.value) ? condition.value : []}
                onChange={(nextTags) => onChange({ ...condition, value: nextTags })}
                placeholder="Select tags"
                ariaLabel="Rule tags"
                allowCreate={false}
              />
            </label>
          </div>
        ) : null}

        {condition.field === "is_internal_transfer" ? (
          <label className="field min-w-0">
            <span>Value</span>
            <NativeSelect
              value={String(Boolean(condition.value))}
              onChange={(event) =>
                onChange({
                  ...condition,
                  value: event.target.value === "true"
                })
              }
            >
              <option value="false">No</option>
              <option value="true">Yes</option>
            </NativeSelect>
          </label>
        ) : null}

        {onRemove ? (
          <div className="flex items-start justify-end lg:pt-6">
            <Button type="button" variant="ghost" size="sm" disabled={disableRemove} onClick={onRemove}>
              {removeLabel}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

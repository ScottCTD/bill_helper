/**
 * CALLING SPEC:
 * - Purpose: render the `FilterGroupEditorCard` React UI module.
 * - Inputs: callers that import `frontend/src/features/filterGroups/FilterGroupEditorCard.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `FilterGroupEditorCard`.
 * - Side effects: React rendering and user event wiring.
 */
import { useEffect, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Textarea } from "../../components/ui/textarea";
import type {
  FilterGroup,
  FilterGroupRule,
  FilterRuleCondition,
  FilterRuleField,
  FilterRuleGroup,
  FilterRuleNode
} from "../../lib/types";

type EditorSubmitPayload = {
  name: string;
  description: string | null;
  color: string | null;
  rule: FilterGroupRule;
};

interface FilterGroupEditorCardProps {
  filterGroup?: FilterGroup;
  submitLabel: string;
  isPending?: boolean;
  errorMessage?: string | null;
  onSubmit: (payload: EditorSubmitPayload) => void;
  onCancel?: () => void;
  onDelete?: () => void;
}

function buildDefaultRule(): FilterGroupRule {
  return {
    include: {
      type: "group",
      operator: "AND",
      children: [
        { type: "condition", field: "entry_kind", operator: "is", value: "EXPENSE" },
        { type: "condition", field: "tags", operator: "has_any", value: ["needs_review"] }
      ]
    },
    exclude: null
  };
}

function createDefaultCondition(field: FilterRuleField = "entry_kind"): FilterRuleCondition {
  if (field === "tags") {
    return { type: "condition", field, operator: "has_any", value: ["needs_review"] };
  }
  if (field === "is_internal_transfer") {
    return { type: "condition", field, operator: "is", value: false };
  }
  return { type: "condition", field, operator: "is", value: "EXPENSE" };
}

function createEmptyGroup(): FilterRuleGroup {
  return { type: "group", operator: "AND", children: [createDefaultCondition()] };
}

function normalizeRule(rule: FilterGroupRule): FilterGroupRule {
  return {
    include: normalizeGroup(rule.include),
    exclude: rule.exclude ? normalizeGroup(rule.exclude) : null
  };
}

function normalizeGroup(group: FilterRuleGroup): FilterRuleGroup {
  return {
    ...group,
    children: group.children.length > 0 ? group.children.map(normalizeNode) : [createDefaultCondition()]
  };
}

function normalizeNode(node: FilterRuleNode): FilterRuleNode {
  if (node.type === "group") {
    return normalizeGroup(node);
  }
  if (node.field === "tags") {
    const values = Array.isArray(node.value)
      ? node.value.map((item) => String(item).trim()).filter(Boolean)
      : [];
    return {
      ...node,
      operator: node.operator === "has_none" ? "has_none" : "has_any",
      value: values.length > 0 ? values : ["needs_review"]
    };
  }
  if (node.field === "is_internal_transfer") {
    return { ...node, operator: "is", value: Boolean(node.value) };
  }
  return { ...node, operator: "is", value: typeof node.value === "string" ? node.value : "EXPENSE" };
}

function conditionLabel(condition: FilterRuleCondition): string {
  if (condition.field === "entry_kind") {
    return `kind is ${String(condition.value).toLowerCase()}`;
  }
  if (condition.field === "is_internal_transfer") {
    return Boolean(condition.value) ? "is internal transfer" : "is not internal transfer";
  }
  return `${condition.operator === "has_none" ? "tags exclude" : "tags include"} ${Array.isArray(condition.value) ? condition.value.join(", ") : ""}`;
}

function ConditionEditor({
  condition,
  onChange,
  onRemove,
  disableRemove
}: {
  condition: FilterRuleCondition;
  onChange: (next: FilterRuleCondition) => void;
  onRemove: () => void;
  disableRemove: boolean;
}) {
  const tagValues = Array.isArray(condition.value) ? condition.value.join(", ") : "";

  return (
    <div className="space-y-3 rounded-lg border border-border/70 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Badge variant="secondary">{conditionLabel(condition)}</Badge>
        <Button type="button" variant="ghost" size="sm" onClick={onRemove} disabled={disableRemove}>
          Remove
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <label className="field">
          <span>Field</span>
          <select
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={condition.field}
            onChange={(event) => onChange(createDefaultCondition(event.target.value as FilterRuleField))}
          >
            <option value="entry_kind">Entry kind</option>
            <option value="tags">Tags</option>
            <option value="is_internal_transfer">Internal transfer</option>
          </select>
        </label>

        {condition.field === "entry_kind" ? (
          <label className="field">
            <span>Value</span>
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={String(condition.value)}
              onChange={(event) => onChange({ ...condition, value: event.target.value })}
            >
              <option value="EXPENSE">Expense</option>
              <option value="INCOME">Income</option>
              <option value="TRANSFER">Transfer</option>
            </select>
          </label>
        ) : null}

        {condition.field === "tags" ? (
          <>
            <label className="field">
              <span>Operator</span>
              <select
                className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={condition.operator}
                onChange={(event) =>
                  onChange({
                    ...condition,
                    operator: event.target.value as FilterRuleCondition["operator"]
                  })
                }
              >
                <option value="has_any">Contains any</option>
                <option value="has_none">Contains none</option>
              </select>
            </label>
            <label className="field md:col-span-2">
              <span>Tags</span>
              <Input
                value={tagValues}
                onChange={(event) =>
                  onChange({
                    ...condition,
                    value: event.target.value
                      .split(",")
                      .map((item) => item.trim())
                      .filter(Boolean)
                  })
                }
                placeholder="grocery, coffee_snacks"
              />
            </label>
          </>
        ) : null}

        {condition.field === "is_internal_transfer" ? (
          <label className="field">
            <span>Value</span>
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={String(Boolean(condition.value))}
              onChange={(event) =>
                onChange({
                  ...condition,
                  value: event.target.value === "true"
                })
              }
            >
              <option value="false">False</option>
              <option value="true">True</option>
            </select>
          </label>
        ) : null}
      </div>
    </div>
  );
}

function RuleNodeEditor({
  node,
  onChange,
  onRemove,
  disableRemove
}: {
  node: FilterRuleNode;
  onChange: (next: FilterRuleNode) => void;
  onRemove: () => void;
  disableRemove: boolean;
}) {
  if (node.type === "group") {
    return <RuleGroupEditor group={node} onChange={onChange} onRemove={onRemove} disableRemove={disableRemove} />;
  }
  return <ConditionEditor condition={node} onChange={onChange} onRemove={onRemove} disableRemove={disableRemove} />;
}

function RuleGroupEditor({
  group,
  onChange,
  onRemove,
  disableRemove
}: {
  group: FilterRuleGroup;
  onChange: (next: FilterRuleGroup) => void;
  onRemove: () => void;
  disableRemove: boolean;
}) {
  function updateChild(index: number, nextNode: FilterRuleNode) {
    onChange({
      ...group,
      children: group.children.map((child, childIndex) => (childIndex === index ? nextNode : child))
    });
  }

  function removeChild(index: number) {
    const nextChildren = group.children.filter((_, childIndex) => childIndex !== index);
    onChange({
      ...group,
      children: nextChildren.length > 0 ? nextChildren : [createDefaultCondition()]
    });
  }

  return (
    <div className="space-y-3 rounded-lg border border-border/70 bg-muted/20 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="field min-w-[180px]">
          <span>Match logic</span>
          <select
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={group.operator}
            onChange={(event) =>
              onChange({
                ...group,
                operator: event.target.value as FilterRuleGroup["operator"]
              })
            }
          >
            <option value="AND">All conditions</option>
            <option value="OR">Any condition</option>
          </select>
        </label>

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onChange({ ...group, children: [...group.children, createDefaultCondition()] })}
          >
            Add condition
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onChange({ ...group, children: [...group.children, createEmptyGroup()] })}
          >
            Add group
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onRemove} disabled={disableRemove}>
            Remove group
          </Button>
        </div>
      </div>

      <div className="space-y-3">
        {group.children.map((child, index) => (
          <RuleNodeEditor
            key={`${child.type}-${index}`}
            node={child}
            onChange={(nextNode) => updateChild(index, nextNode)}
            onRemove={() => removeChild(index)}
            disableRemove={group.children.length <= 1}
          />
        ))}
      </div>
    </div>
  );
}

export function FilterGroupEditorCard({
  filterGroup,
  submitLabel,
  isPending = false,
  errorMessage,
  onSubmit,
  onCancel,
  onDelete
}: FilterGroupEditorCardProps) {
  const [name, setName] = useState(filterGroup?.name ?? "");
  const [description, setDescription] = useState(filterGroup?.description ?? "");
  const [color, setColor] = useState(filterGroup?.color ?? "#64748b");
  const [rule, setRule] = useState<FilterGroupRule>(filterGroup?.rule ?? buildDefaultRule());

  useEffect(() => {
    setName(filterGroup?.name ?? "");
    setDescription(filterGroup?.description ?? "");
    setColor(filterGroup?.color ?? "#64748b");
    setRule(filterGroup?.rule ?? buildDefaultRule());
  }, [filterGroup]);

  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>{filterGroup ? filterGroup.name : "New filter group"}</CardTitle>
          <div className="flex flex-wrap gap-2">
            {filterGroup ? <Badge variant={filterGroup.is_default ? "secondary" : "outline"}>{filterGroup.is_default ? "Default" : "Custom"}</Badge> : null}
            {filterGroup?.rule_summary ? <Badge variant="outline">{filterGroup.rule_summary}</Badge> : null}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr),180px]">
          <label className="field">
            <span>Name</span>
            <Input value={name} onChange={(event) => setName(event.target.value)} disabled={Boolean(filterGroup?.is_default)} />
          </label>
          <label className="field">
            <span>Chart color</span>
            <Input type="color" value={color} onChange={(event) => setColor(event.target.value)} />
          </label>
        </div>

        <label className="field">
          <span>Description</span>
          <Textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Explain what this group means to you."
            rows={2}
          />
        </label>
      </CardHeader>

      <CardContent className="space-y-4">
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Include when</h3>
          </div>
          <RuleGroupEditor group={rule.include} onChange={(next) => setRule((current) => ({ ...current, include: normalizeGroup(next) }))} onRemove={() => undefined} disableRemove />
        </section>

        <section className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">Exclude when</h3>
            {rule.exclude ? (
              <Button type="button" variant="ghost" size="sm" onClick={() => setRule((current) => ({ ...current, exclude: null }))}>
                Remove exclusion
              </Button>
            ) : (
              <Button type="button" variant="outline" size="sm" onClick={() => setRule((current) => ({ ...current, exclude: createEmptyGroup() }))}>
                Add exclusion
              </Button>
            )}
          </div>
          {rule.exclude ? (
            <RuleGroupEditor
              group={rule.exclude}
              onChange={(next) => setRule((current) => ({ ...current, exclude: normalizeGroup(next) }))}
              onRemove={() => setRule((current) => ({ ...current, exclude: null }))}
              disableRemove={false}
            />
          ) : (
            <p className="muted text-sm">No exclusions.</p>
          )}
        </section>

        {errorMessage ? <p className="error">{errorMessage}</p> : null}

        <div className="flex flex-wrap justify-end gap-2">
          {onDelete ? (
            <Button type="button" variant="outline" onClick={onDelete} disabled={isPending}>
              Delete
            </Button>
          ) : null}
          {onCancel ? (
            <Button type="button" variant="ghost" onClick={onCancel} disabled={isPending}>
              Cancel
            </Button>
          ) : null}
          <Button
            type="button"
            onClick={() =>
              onSubmit({
                name: name.trim(),
                description: description.trim() || null,
                color: color || null,
                rule: normalizeRule(rule)
              })
            }
            disabled={isPending || !name.trim()}
          >
            {submitLabel}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

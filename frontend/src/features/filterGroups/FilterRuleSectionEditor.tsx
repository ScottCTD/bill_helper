/**
 * CALLING SPEC:
 * - Purpose: render one filter-rule section with guided and advanced editing modes.
 * - Inputs: callers that provide one include/exclude rule group plus tag catalog data.
 * - Outputs: React UI for editing one rule section.
 * - Side effects: React rendering and user event wiring.
 */
import { useEffect, useState } from "react";

import { Button } from "../../components/ui/button";
import { NativeSelect } from "../../components/ui/native-select";
import type { FilterRuleCondition, FilterRuleGroup, FilterRuleNode, Tag } from "../../lib/types";
import { cn } from "../../lib/utils";
import { FilterRuleConditionRow } from "./FilterRuleConditionRow";
import {
  containsNestedGroups,
  createDefaultCondition,
  createEmptyGroup,
  normalizeGroup,
  normalizeNode
} from "./filterGroupRuleUtils";

type RuleSectionMode = "guided" | "advanced";

interface FilterRuleSectionEditorProps {
  title: string;
  description: string;
  group: FilterRuleGroup;
  tags: Tag[];
  preferredTagName?: string;
  removeSectionLabel?: string;
  onChange: (next: FilterRuleGroup) => void;
  onRemoveSection?: () => void;
}

function GuidedRuleEditor({
  group,
  tags,
  preferredTagName,
  onChange
}: {
  group: FilterRuleGroup;
  tags: Tag[];
  preferredTagName?: string;
  onChange: (next: FilterRuleGroup) => void;
}) {
  const conditions = group.children as FilterRuleCondition[];

  function updateCondition(index: number, nextCondition: FilterRuleCondition) {
    onChange({
      ...group,
      children: group.children.map((child, childIndex) => (childIndex === index ? nextCondition : child))
    });
  }

  function removeCondition(index: number) {
    const nextChildren = group.children.filter((_, childIndex) => childIndex !== index);
    onChange({
      ...group,
      children: nextChildren.length > 0 ? nextChildren : [createDefaultCondition("entry_kind", preferredTagName)]
    });
  }

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3 rounded-xl border border-border/80 bg-secondary/35 p-3">
        <label className="field min-w-[180px]">
          <span>Match using</span>
          <NativeSelect
            value={group.operator}
            onChange={(event) =>
              onChange({
                ...group,
                operator: event.target.value as FilterRuleGroup["operator"]
              })
            }
          >
            <option value="AND">AND</option>
            <option value="OR">OR</option>
          </NativeSelect>
        </label>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() =>
            onChange({
              ...group,
              children: [...group.children, createDefaultCondition("entry_kind", preferredTagName)]
            })
          }
        >
          Add condition
        </Button>
      </div>

      <div className="grid gap-3">
        {conditions.map((condition, index) => (
          <FilterRuleConditionRow
            key={`guided-condition-${index}`}
            condition={condition}
            tags={tags}
            preferredTagName={preferredTagName}
            disableRemove={conditions.length <= 1}
            onChange={(nextCondition) => updateCondition(index, nextCondition)}
            onRemove={() => removeCondition(index)}
          />
        ))}
      </div>
    </div>
  );
}

function AdvancedRuleNodeEditor({
  node,
  isRoot,
  tags,
  preferredTagName,
  onChange,
  onRemove
}: {
  node: FilterRuleNode;
  isRoot?: boolean;
  tags: Tag[];
  preferredTagName?: string;
  onChange: (next: FilterRuleNode) => void;
  onRemove: () => void;
}) {
  if (node.type === "group") {
    return (
      <AdvancedRuleGroupEditor
        group={node}
        isRoot={Boolean(isRoot)}
        tags={tags}
        preferredTagName={preferredTagName}
        onChange={onChange}
        onRemove={onRemove}
      />
    );
  }

  return (
    <FilterRuleConditionRow
      condition={node}
      tags={tags}
      preferredTagName={preferredTagName}
      removeLabel="Remove"
      onChange={(nextCondition) => onChange(nextCondition)}
      onRemove={onRemove}
    />
  );
}

function AdvancedRuleGroupEditor({
  group,
  isRoot = false,
  tags,
  preferredTagName,
  onChange,
  onRemove
}: {
  group: FilterRuleGroup;
  isRoot?: boolean;
  tags: Tag[];
  preferredTagName?: string;
  onChange: (next: FilterRuleGroup) => void;
  onRemove: () => void;
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
      children: nextChildren.length > 0 ? nextChildren : [createDefaultCondition("entry_kind", preferredTagName)]
    });
  }

  return (
    <div
      className={cn(
        "grid gap-3 rounded-xl border border-border p-3",
        isRoot ? "bg-secondary/35" : "bg-background"
      )}
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <label className="field min-w-[180px]">
          <span>{isRoot ? "Match using" : "Nested group logic"}</span>
          <NativeSelect
            value={group.operator}
            onChange={(event) =>
              onChange({
                ...group,
                operator: event.target.value as FilterRuleGroup["operator"]
              })
            }
          >
            <option value="AND">AND</option>
            <option value="OR">OR</option>
          </NativeSelect>
        </label>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              onChange({
                ...group,
                children: [...group.children, createDefaultCondition("entry_kind", preferredTagName)]
              })
            }
          >
            Add condition
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              onChange({
                ...group,
                children: [...group.children, createEmptyGroup("entry_kind", preferredTagName)]
              })
            }
          >
            Add group
          </Button>
          {!isRoot ? (
            <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
              Remove group
            </Button>
          ) : null}
        </div>
      </div>

      <div className="grid gap-3">
        {group.children.map((child, index) => (
          <AdvancedRuleNodeEditor
            key={`advanced-${child.type}-${index}`}
            node={child}
            tags={tags}
            preferredTagName={preferredTagName}
            onChange={(nextNode) => updateChild(index, nextNode)}
            onRemove={() => removeChild(index)}
          />
        ))}
      </div>
    </div>
  );
}

export function FilterRuleSectionEditor({
  title,
  description,
  group,
  tags,
  preferredTagName,
  removeSectionLabel = "Remove section",
  onChange,
  onRemoveSection
}: FilterRuleSectionEditorProps) {
  const hasNestedGroups = containsNestedGroups(group);
  const [mode, setMode] = useState<RuleSectionMode>(() => (hasNestedGroups ? "advanced" : "guided"));

  useEffect(() => {
    if (hasNestedGroups) {
      setMode("advanced");
    }
  }, [hasNestedGroups]);

  function updateGroup(nextGroup: FilterRuleGroup) {
    onChange(normalizeGroup(nextGroup, preferredTagName));
  }

  return (
    <section className="grid gap-3 rounded-2xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={mode === "guided" ? "secondary" : "outline"}
            disabled={hasNestedGroups}
            onClick={() => setMode("guided")}
          >
            Guided
          </Button>
          <Button type="button" size="sm" variant={mode === "advanced" ? "secondary" : "outline"} onClick={() => setMode("advanced")}>
            Advanced
          </Button>
          {onRemoveSection ? (
            <Button type="button" size="sm" variant="ghost" onClick={onRemoveSection}>
              {removeSectionLabel}
            </Button>
          ) : null}
        </div>
      </div>

      {hasNestedGroups ? (
        <p className="rounded-lg border border-border/80 bg-secondary/35 px-3 py-2 text-sm text-muted-foreground">
          This section already uses nested groups, so guided mode stays locked until the nested structure is removed in advanced mode.
        </p>
      ) : null}

      {mode === "guided" && !hasNestedGroups ? (
        <GuidedRuleEditor group={group} tags={tags} preferredTagName={preferredTagName} onChange={updateGroup} />
      ) : (
        <AdvancedRuleGroupEditor
          group={normalizeNode(group, preferredTagName) as FilterRuleGroup}
          isRoot
          tags={tags}
          preferredTagName={preferredTagName}
          onChange={updateGroup}
          onRemove={() => undefined}
        />
      )}
    </section>
  );
}

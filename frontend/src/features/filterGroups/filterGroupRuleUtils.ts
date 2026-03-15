/**
 * CALLING SPEC:
 * - Purpose: provide normalized rule-building helpers for the filter-groups editor.
 * - Inputs: frontend callers that create, inspect, or sanitize filter-group rules.
 * - Outputs: pure helper functions and editor-friendly defaults.
 * - Side effects: none.
 */
import type {
  FilterGroupRule,
  FilterRuleCondition,
  FilterRuleField,
  FilterRuleGroup,
  FilterRuleNode
} from "../../lib/types";

const FALLBACK_TAG_NAME = "needs_review";

function normalizeTagValue(value: unknown): string | null {
  const normalized = String(value ?? "").trim().toLowerCase();
  return normalized || null;
}

function normalizeTagList(values: unknown[]): string[] {
  const seen = new Set<string>();
  const normalizedValues: string[] = [];
  for (const value of values) {
    const normalized = normalizeTagValue(value);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    normalizedValues.push(normalized);
  }
  return normalizedValues;
}

export function createDefaultCondition(
  field: FilterRuleField = "entry_kind",
  preferredTagName?: string
): FilterRuleCondition {
  if (field === "tags") {
    const fallbackTagName = normalizeTagValue(preferredTagName) ?? FALLBACK_TAG_NAME;
    return {
      type: "condition",
      field,
      operator: "has_any",
      value: [fallbackTagName]
    };
  }

  if (field === "is_internal_transfer") {
    return {
      type: "condition",
      field,
      operator: "is",
      value: true
    };
  }

  return {
    type: "condition",
    field,
    operator: "is",
    value: "EXPENSE"
  };
}

export function createEmptyGroup(
  preferredField: FilterRuleField = "entry_kind",
  preferredTagName?: string
): FilterRuleGroup {
  return {
    type: "group",
    operator: "AND",
    children: [createDefaultCondition(preferredField, preferredTagName)]
  };
}

export function buildDefaultRule(preferredTagName?: string): FilterGroupRule {
  return {
    include: createEmptyGroup("entry_kind", preferredTagName),
    exclude: null
  };
}

export function normalizeRule(rule: FilterGroupRule, preferredTagName?: string): FilterGroupRule {
  return {
    include: normalizeGroup(rule.include, preferredTagName),
    exclude: rule.exclude ? normalizeGroup(rule.exclude, preferredTagName) : null
  };
}

export function normalizeGroup(group: FilterRuleGroup, preferredTagName?: string): FilterRuleGroup {
  return {
    ...group,
    operator: group.operator === "OR" ? "OR" : "AND",
    children:
      group.children.length > 0
        ? group.children.map((child) => normalizeNode(child, preferredTagName))
        : [createDefaultCondition("entry_kind", preferredTagName)]
  };
}

export function normalizeNode(node: FilterRuleNode, preferredTagName?: string): FilterRuleNode {
  if (node.type === "group") {
    return normalizeGroup(node, preferredTagName);
  }

  if (node.field === "tags") {
    const normalizedValues = Array.isArray(node.value) ? normalizeTagList(node.value) : [];
    return {
      ...node,
      operator: node.operator === "has_none" ? "has_none" : "has_any",
      value: normalizedValues.length > 0 ? normalizedValues : [normalizeTagValue(preferredTagName) ?? FALLBACK_TAG_NAME]
    };
  }

  if (node.field === "is_internal_transfer") {
    return {
      ...node,
      operator: "is",
      value: Boolean(node.value)
    };
  }

  return {
    ...node,
    operator: "is",
    value: typeof node.value === "string" ? node.value : "EXPENSE"
  };
}

export function containsNestedGroups(group: FilterRuleGroup): boolean {
  return group.children.some((child) => child.type === "group");
}

export function createConditionForField(
  field: FilterRuleField,
  current: FilterRuleCondition | null,
  preferredTagName?: string
): FilterRuleCondition {
  if (current?.field === field) {
    return normalizeNode(current, preferredTagName) as FilterRuleCondition;
  }
  return createDefaultCondition(field, preferredTagName);
}

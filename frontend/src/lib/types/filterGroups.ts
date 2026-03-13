/**
 * CALLING SPEC:
 * - Purpose: define filter-group rule and summary contracts for the frontend.
 * - Inputs: frontend modules that build or render filter-group rules.
 * - Outputs: filter-group rule interfaces and read models.
 * - Side effects: type declarations only.
 */

export type FilterRuleField = "entry_kind" | "tags" | "is_internal_transfer";
export type FilterRuleConditionOperator = "is" | "has_any" | "has_none";
export type FilterRuleLogicalOperator = "AND" | "OR";

export interface FilterRuleCondition {
  type: "condition";
  field: FilterRuleField;
  operator: FilterRuleConditionOperator;
  value: string | boolean | string[];
}

export interface FilterRuleGroup {
  type: "group";
  operator: FilterRuleLogicalOperator;
  children: FilterRuleNode[];
}

export type FilterRuleNode = FilterRuleCondition | FilterRuleGroup;

export interface FilterGroupRule {
  include: FilterRuleGroup;
  exclude: FilterRuleGroup | null;
}

export interface FilterGroup {
  id: string;
  key: string;
  name: string;
  description: string | null;
  color: string | null;
  is_default: boolean;
  position: number;
  rule: FilterGroupRule;
  rule_summary: string;
  created_at: string;
  updated_at: string;
}

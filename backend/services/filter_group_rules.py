# CALLING SPEC:
# - Purpose: implement focused service logic for `filter_group_rules`.
# - Inputs: callers that import `backend/services/filter_group_rules.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `filter_group_rules`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from dataclasses import dataclass

from backend.enums_finance import EntryKind
from backend.schemas_finance import (
    FilterGroupRule,
    FilterRuleCondition,
    FilterRuleGroup,
    FilterRuleNode,
)


@dataclass(frozen=True, slots=True)
class FilterEntryContext:
    kind: EntryKind
    tag_names: frozenset[str]
    is_internal_transfer: bool


def evaluate_filter_group_rule(rule: FilterGroupRule, context: FilterEntryContext) -> bool:
    if not _evaluate_group(rule.include, context):
        return False
    if rule.exclude is not None and _evaluate_group(rule.exclude, context):
        return False
    return True


def summarize_filter_group_rule(rule: FilterGroupRule) -> str:
    include_summary = _summarize_group(rule.include)
    if rule.exclude is None:
        return include_summary
    return f"{include_summary}; excluding {_summarize_group(rule.exclude)}"


def _evaluate_group(group: FilterRuleGroup, context: FilterEntryContext) -> bool:
    results = [_evaluate_node(child, context) for child in group.children]
    return all(results) if group.operator == "AND" else any(results)


def _evaluate_node(node: FilterRuleNode, context: FilterEntryContext) -> bool:
    if isinstance(node, FilterRuleGroup):
        return _evaluate_group(node, context)
    return _evaluate_condition(node, context)


def _evaluate_condition(condition: FilterRuleCondition, context: FilterEntryContext) -> bool:
    if condition.field == "entry_kind":
        return context.kind == EntryKind(str(condition.value))
    if condition.field == "is_internal_transfer":
        return context.is_internal_transfer is bool(condition.value)
    tag_values = frozenset(str(value) for value in condition.value) if isinstance(condition.value, list) else frozenset()
    if condition.operator == "has_any":
        return bool(context.tag_names & tag_values)
    if condition.operator == "has_none":
        return not bool(context.tag_names & tag_values)
    return False


def _summarize_group(group: FilterRuleGroup) -> str:
    joiner = " and " if group.operator == "AND" else " or "
    parts = [_summarize_node(child) for child in group.children]
    if len(parts) == 1:
        return parts[0]
    return f"({joiner.join(parts)})"


def _summarize_node(node: FilterRuleNode) -> str:
    if isinstance(node, FilterRuleGroup):
        return _summarize_group(node)
    return _summarize_condition(node)


def _summarize_condition(condition: FilterRuleCondition) -> str:
    if condition.field == "entry_kind":
        return f"kind is {str(condition.value).lower()}"
    if condition.field == "is_internal_transfer":
        return "is an internal transfer" if bool(condition.value) else "is not an internal transfer"
    values = [str(value) for value in condition.value] if isinstance(condition.value, list) else []
    if condition.operator == "has_any":
        return f"tags include {_join_values(values)}"
    return f"tags exclude {_join_values(values)}"


def _join_values(values: list[str]) -> str:
    if not values:
        return "(none)"
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} or {values[1]}"
    return f"{', '.join(values[:-1])}, or {values[-1]}"

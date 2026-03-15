/**
 * CALLING SPEC:
 * - Purpose: provide selection and dirty-state helpers for the filters workspace editor.
 * - Inputs: frontend callers that manage filter-group editor sessions.
 * - Outputs: pure session helpers and submit-payload builders.
 * - Side effects: none.
 */
import type { FilterGroup, FilterGroupRule } from "../../lib/types";
import { buildDefaultRule, normalizeRule } from "./filterGroupRuleUtils";

export const DEFAULT_FILTER_GROUP_COLOR = "#64748b";
export const UNTAGGED_FILTER_GROUP_KEY = "untagged";

export type FilterGroupEditorTarget = { kind: "new" } | { kind: "existing"; filterGroupId: string };

export interface FilterGroupEditorFormState {
  name: string;
  description: string;
  color: string;
  rule: FilterGroupRule;
}

export type FilterGroupEditorSession =
  | {
      kind: "new";
      isDefault: false;
      formState: FilterGroupEditorFormState;
      baselineState: FilterGroupEditorFormState;
    }
  | {
      kind: "existing";
      filterGroupId: string;
      filterGroupKey: string;
      isDefault: boolean;
      formState: FilterGroupEditorFormState;
      baselineState: FilterGroupEditorFormState;
    };

function serializeFormState(formState: FilterGroupEditorFormState): string {
  return JSON.stringify({
    name: formState.name.trim(),
    description: formState.description.trim(),
    color: formState.color,
    rule: normalizeRule(formState.rule)
  });
}

export function buildFormState(
  filterGroup?: Pick<FilterGroup, "name" | "description" | "color" | "rule">
): FilterGroupEditorFormState {
  return {
    name: filterGroup?.name ?? "",
    description: filterGroup?.description ?? "",
    color: filterGroup?.color ?? DEFAULT_FILTER_GROUP_COLOR,
    rule: normalizeRule(filterGroup?.rule ?? buildDefaultRule())
  };
}

export function createNewEditorSession(): FilterGroupEditorSession {
  const formState = buildFormState();
  return {
    kind: "new",
    isDefault: false,
    formState,
    baselineState: formState
  };
}

export function createExistingEditorSession(filterGroup: FilterGroup): FilterGroupEditorSession {
  const formState = buildFormState(filterGroup);
  return {
    kind: "existing",
    filterGroupId: filterGroup.id,
    filterGroupKey: filterGroup.key,
    isDefault: filterGroup.is_default,
    formState,
    baselineState: formState
  };
}

export function updateSessionFormState(
  session: FilterGroupEditorSession,
  formState: FilterGroupEditorFormState
): FilterGroupEditorSession {
  return {
    ...session,
    formState
  };
}

export function isEditorSessionDirty(session: FilterGroupEditorSession): boolean {
  return serializeFormState(session.formState) !== serializeFormState(session.baselineState);
}

export function isSameEditorTarget(
  session: FilterGroupEditorSession | null,
  target: FilterGroupEditorTarget
): boolean {
  if (!session) {
    return false;
  }
  if (session.kind !== target.kind) {
    return false;
  }
  if (target.kind === "new") {
    return true;
  }
  return session.kind === "existing" && session.filterGroupId === target.filterGroupId;
}

export function toFilterGroupSubmitPayload(formState: FilterGroupEditorFormState) {
  return {
    name: formState.name.trim(),
    description: formState.description.trim() || null,
    color: formState.color || null,
    rule: normalizeRule(formState.rule)
  };
}

export function pickNextFilterGroupId(filterGroups: FilterGroup[], deletedFilterGroupId: string): string | null {
  const deletedIndex = filterGroups.findIndex((filterGroup) => filterGroup.id === deletedFilterGroupId);
  if (deletedIndex < 0) {
    return filterGroups[0]?.id ?? null;
  }
  return filterGroups[deletedIndex + 1]?.id ?? filterGroups[deletedIndex - 1]?.id ?? null;
}


export function isSystemUntaggedSession(session: FilterGroupEditorSession | null): boolean {
  return session?.kind === "existing" && session.filterGroupKey === UNTAGGED_FILTER_GROUP_KEY;
}

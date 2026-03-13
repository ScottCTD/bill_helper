/**
 * CALLING SPEC:
 * - Purpose: provide the `types` frontend module.
 * - Inputs: callers that import `frontend/src/features/properties/types.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `types`.
 * - Side effects: module-local frontend behavior only.
 */
export type PropertiesSectionId = "tags" | "currencies" | "entityCategories" | "tagCategories";

export const SECTION_SEARCH_DEFAULTS: Record<PropertiesSectionId, string> = {
  tags: "",
  currencies: "",
  entityCategories: "",
  tagCategories: ""
};

export const SECTION_CREATE_PANEL_DEFAULTS: Record<PropertiesSectionId, boolean> = {
  tags: false,
  currencies: false,
  entityCategories: false,
  tagCategories: false
};

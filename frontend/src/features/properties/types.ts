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

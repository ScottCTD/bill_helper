export type PropertiesSectionId = "users" | "tags" | "currencies" | "entityCategories" | "tagCategories";

export const SECTION_SEARCH_DEFAULTS: Record<PropertiesSectionId, string> = {
  users: "",
  tags: "",
  currencies: "",
  entityCategories: "",
  tagCategories: ""
};

export const SECTION_CREATE_PANEL_DEFAULTS: Record<PropertiesSectionId, boolean> = {
  users: false,
  tags: false,
  currencies: false,
  entityCategories: false,
  tagCategories: false
};

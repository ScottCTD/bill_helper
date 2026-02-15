export const ENTITY_CATEGORY_TAXONOMY_KEY = "entity_category";
export const TAG_CATEGORY_TAXONOMY_KEY = "tag_category";

export type PropertiesSectionId = "users" | "entities" | "tags" | "currencies" | "entityCategories" | "tagCategories";

export const SECTION_SEARCH_DEFAULTS: Record<PropertiesSectionId, string> = {
  users: "",
  entities: "",
  tags: "",
  currencies: "",
  entityCategories: "",
  tagCategories: ""
};

export const SECTION_CREATE_PANEL_DEFAULTS: Record<PropertiesSectionId, boolean> = {
  users: false,
  entities: false,
  tags: false,
  currencies: false,
  entityCategories: false,
  tagCategories: false
};

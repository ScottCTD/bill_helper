export const ENTITY_CATEGORY_TAXONOMY_KEY = "entity_category";
export const TAG_TYPE_TAXONOMY_KEY = "tag_type";

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

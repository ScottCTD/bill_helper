import { useMemo } from "react";

import type { Currency, Entity, Tag, TaxonomyTerm, User } from "../../lib/types";
import { includesFilter } from "./helpers";
import type { PropertiesSectionId } from "./types";

interface PropertiesFilteredDataArgs {
  sectionSearch: Record<PropertiesSectionId, string>;
  users: User[] | undefined;
  entities: Entity[] | undefined;
  tags: Tag[] | undefined;
  currencies: Currency[] | undefined;
  entityCategoryTerms: TaxonomyTerm[] | undefined;
  tagTypeTerms: TaxonomyTerm[] | undefined;
}

export function usePropertiesFilteredData(args: PropertiesFilteredDataArgs) {
  const {
    sectionSearch,
    users,
    entities,
    tags,
    currencies,
    entityCategoryTerms,
    tagTypeTerms
  } = args;

  const filteredUsers = useMemo(() => {
    return (users ?? []).filter((user) => includesFilter(user.name, sectionSearch.users));
  }, [sectionSearch.users, users]);

  const filteredEntities = useMemo(() => {
    return (entities ?? []).filter(
      (entity) => includesFilter(entity.name, sectionSearch.entities) || includesFilter(entity.category, sectionSearch.entities)
    );
  }, [entities, sectionSearch.entities]);

  const filteredTags = useMemo(() => {
    return (tags ?? []).filter(
      (tag) =>
        includesFilter(tag.name, sectionSearch.tags) ||
        includesFilter(tag.type, sectionSearch.tags) ||
        includesFilter(tag.color, sectionSearch.tags) ||
        includesFilter(tag.description, sectionSearch.tags)
    );
  }, [sectionSearch.tags, tags]);

  const filteredCurrencies = useMemo(() => {
    return (currencies ?? []).filter(
      (currency) =>
        includesFilter(currency.code, sectionSearch.currencies) || includesFilter(currency.name, sectionSearch.currencies)
    );
  }, [currencies, sectionSearch.currencies]);

  const filteredEntityCategoryTerms = useMemo(() => {
    return (entityCategoryTerms ?? []).filter((term) => includesFilter(term.name, sectionSearch.entityCategories));
  }, [entityCategoryTerms, sectionSearch.entityCategories]);

  const filteredTagTypeTerms = useMemo(() => {
    return (tagTypeTerms ?? []).filter((term) => includesFilter(term.name, sectionSearch.tagCategories));
  }, [sectionSearch.tagCategories, tagTypeTerms]);

  return {
    users: filteredUsers,
    entities: filteredEntities,
    tags: filteredTags,
    currencies: filteredCurrencies,
    entityCategoryTerms: filteredEntityCategoryTerms,
    tagTypeTerms: filteredTagTypeTerms
  };
}

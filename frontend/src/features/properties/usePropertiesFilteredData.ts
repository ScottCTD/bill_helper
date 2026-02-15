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
  tagCategoryTerms: TaxonomyTerm[] | undefined;
}

export function usePropertiesFilteredData(args: PropertiesFilteredDataArgs) {
  const {
    sectionSearch,
    users,
    entities,
    tags,
    currencies,
    entityCategoryTerms,
    tagCategoryTerms
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
        includesFilter(tag.category, sectionSearch.tags) ||
        includesFilter(tag.color, sectionSearch.tags)
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

  const filteredTagCategoryTerms = useMemo(() => {
    return (tagCategoryTerms ?? []).filter((term) => includesFilter(term.name, sectionSearch.tagCategories));
  }, [sectionSearch.tagCategories, tagCategoryTerms]);

  return {
    users: filteredUsers,
    entities: filteredEntities,
    tags: filteredTags,
    currencies: filteredCurrencies,
    entityCategoryTerms: filteredEntityCategoryTerms,
    tagCategoryTerms: filteredTagCategoryTerms
  };
}

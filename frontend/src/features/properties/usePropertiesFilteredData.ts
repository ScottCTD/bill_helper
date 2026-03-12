import { useMemo } from "react";

import type { Currency, Tag, TaxonomyTerm } from "../../lib/types";
import { includesFilter } from "../../lib/catalogs";
import type { PropertiesSectionId } from "./types";

interface PropertiesFilteredDataArgs {
  sectionSearch: Record<PropertiesSectionId, string>;
  tags: Tag[] | undefined;
  currencies: Currency[] | undefined;
  entityCategoryTerms: TaxonomyTerm[] | undefined;
  tagTypeTerms: TaxonomyTerm[] | undefined;
}

export function usePropertiesFilteredData(args: PropertiesFilteredDataArgs) {
  const {
    sectionSearch,
    tags,
    currencies,
    entityCategoryTerms,
    tagTypeTerms
  } = args;

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
    tags: filteredTags,
    currencies: filteredCurrencies,
    entityCategoryTerms: filteredEntityCategoryTerms,
    tagTypeTerms: filteredTagTypeTerms
  };
}

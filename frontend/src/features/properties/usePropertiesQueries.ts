import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  listCurrencies,
  listEntities,
  listTags,
  listTaxonomies,
  listTaxonomyTerms,
  listUsers
} from "../../lib/api";
import { queryKeys } from "../../lib/queryKeys";
import { taxonomyTermNames, uniqueOptionValues } from "./helpers";
import { ENTITY_CATEGORY_TAXONOMY_KEY, TAG_CATEGORY_TAXONOMY_KEY } from "./types";

export function usePropertiesQueries() {
  const entitiesQuery = useQuery({ queryKey: queryKeys.properties.entities, queryFn: listEntities });
  const usersQuery = useQuery({ queryKey: queryKeys.properties.users, queryFn: listUsers });
  const tagsQuery = useQuery({ queryKey: queryKeys.properties.tags, queryFn: listTags });
  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });
  const taxonomiesQuery = useQuery({ queryKey: queryKeys.properties.taxonomies, queryFn: listTaxonomies });
  const entityCategoryTermsQuery = useQuery({
    queryKey: queryKeys.properties.taxonomyTerms(ENTITY_CATEGORY_TAXONOMY_KEY),
    queryFn: () => listTaxonomyTerms(ENTITY_CATEGORY_TAXONOMY_KEY)
  });
  const tagCategoryTermsQuery = useQuery({
    queryKey: queryKeys.properties.taxonomyTerms(TAG_CATEGORY_TAXONOMY_KEY),
    queryFn: () => listTaxonomyTerms(TAG_CATEGORY_TAXONOMY_KEY)
  });

  const entityCategoryOptions = useMemo(
    () =>
      uniqueOptionValues([
        ...taxonomyTermNames(entityCategoryTermsQuery.data),
        ...(entitiesQuery.data ?? []).map((entity) => entity.category)
      ]),
    [entitiesQuery.data, entityCategoryTermsQuery.data]
  );

  const tagCategoryOptions = useMemo(
    () =>
      uniqueOptionValues([
        ...taxonomyTermNames(tagCategoryTermsQuery.data),
        ...(tagsQuery.data ?? []).map((tag) => tag.category)
      ]),
    [tagCategoryTermsQuery.data, tagsQuery.data]
  );

  const taxonomyDisplayNames = useMemo(() => {
    const labels = new Map<string, string>();
    (taxonomiesQuery.data ?? []).forEach((taxonomy) => labels.set(taxonomy.key, taxonomy.display_name));
    return labels;
  }, [taxonomiesQuery.data]);

  const entityCategoriesLabel = taxonomyDisplayNames.get(ENTITY_CATEGORY_TAXONOMY_KEY) ?? "Entity Categories";
  const tagCategoriesLabel = taxonomyDisplayNames.get(TAG_CATEGORY_TAXONOMY_KEY) ?? "Tag Categories";

  return {
    queries: {
      taxonomiesQuery,
      usersQuery,
      entitiesQuery,
      tagsQuery,
      currenciesQuery,
      entityCategoryTermsQuery,
      tagCategoryTermsQuery
    },
    options: {
      entityCategoryOptions,
      tagCategoryOptions
    },
    labels: {
      entityCategoriesLabel,
      tagCategoriesLabel
    }
  };
}

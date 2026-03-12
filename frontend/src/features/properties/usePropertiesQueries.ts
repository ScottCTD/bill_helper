import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  listCurrencies,
  listTags,
  listTaxonomies,
  listTaxonomyTerms
} from "../../lib/api";
import { ENTITY_CATEGORY_TAXONOMY_KEY, TAG_TYPE_TAXONOMY_KEY, taxonomyTermNames, uniqueOptionValues } from "../../lib/catalogs";
import { queryKeys } from "../../lib/queryKeys";

export function usePropertiesQueries() {
  const tagsQuery = useQuery({ queryKey: queryKeys.properties.tags, queryFn: listTags });
  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });
  const taxonomiesQuery = useQuery({ queryKey: queryKeys.properties.taxonomies, queryFn: listTaxonomies });
  const entityCategoryTermsQuery = useQuery({
    queryKey: queryKeys.properties.taxonomyTerms(ENTITY_CATEGORY_TAXONOMY_KEY),
    queryFn: () => listTaxonomyTerms(ENTITY_CATEGORY_TAXONOMY_KEY)
  });
  const tagTypeTermsQuery = useQuery({
    queryKey: queryKeys.properties.taxonomyTerms(TAG_TYPE_TAXONOMY_KEY),
    queryFn: () => listTaxonomyTerms(TAG_TYPE_TAXONOMY_KEY)
  });

  const tagTypeOptions = useMemo(
    () =>
      uniqueOptionValues([
        ...taxonomyTermNames(tagTypeTermsQuery.data),
        ...(tagsQuery.data ?? []).map((tag) => tag.type)
      ]),
    [tagTypeTermsQuery.data, tagsQuery.data]
  );

  const taxonomyDisplayNames = useMemo(() => {
    const labels = new Map<string, string>();
    (taxonomiesQuery.data ?? []).forEach((taxonomy) => labels.set(taxonomy.key, taxonomy.display_name));
    return labels;
  }, [taxonomiesQuery.data]);

  const entityCategoriesLabel = taxonomyDisplayNames.get(ENTITY_CATEGORY_TAXONOMY_KEY) ?? "Entity Categories";
  const tagTypesLabel = taxonomyDisplayNames.get(TAG_TYPE_TAXONOMY_KEY) ?? "Tag Types";

  return {
    queries: {
      taxonomiesQuery,
      tagsQuery,
      currenciesQuery,
      entityCategoryTermsQuery,
      tagTypeTermsQuery
    },
    options: {
      tagTypeOptions
    },
    labels: {
      entityCategoriesLabel,
      tagTypesLabel
    }
  };
}

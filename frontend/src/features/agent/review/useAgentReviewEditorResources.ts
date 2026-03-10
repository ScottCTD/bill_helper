import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { getRuntimeSettings, listCurrencies, listEntities, listTags } from "../../../lib/api";
import { queryKeys } from "../../../lib/queryKeys";
import type { Currency, Entity, Tag } from "../../../lib/types";

export interface ReviewEditorResources {
  currencies: Currency[];
  entities: Entity[];
  tags: Tag[];
  defaultCurrencyCode: string;
  editorLoadError: string | null;
  entityCategoryOptions: string[];
  tagTypeOptions: string[];
}

export function useAgentReviewEditorResources(open: boolean): ReviewEditorResources {
  const runtimeSettingsQuery = useQuery({
    queryKey: queryKeys.settings.runtime,
    queryFn: getRuntimeSettings,
    enabled: open
  });
  const entitiesQuery = useQuery({
    queryKey: queryKeys.properties.entities,
    queryFn: listEntities,
    enabled: open
  });
  const tagsQuery = useQuery({
    queryKey: queryKeys.properties.tags,
    queryFn: listTags,
    enabled: open
  });
  const currenciesQuery = useQuery({
    queryKey: queryKeys.properties.currencies,
    queryFn: listCurrencies,
    enabled: open
  });

  return useMemo<ReviewEditorResources>(() => {
    const defaultCurrencyCode = runtimeSettingsQuery.data?.default_currency_code ?? "USD";
    const editorLoadError = [runtimeSettingsQuery, entitiesQuery, tagsQuery, currenciesQuery]
      .map((query) => (query.isError ? (query.error as Error).message : null))
      .find((message): message is string => Boolean(message)) ?? null;
    const tagTypeOptions = Array.from(
      new Set(
        (tagsQuery.data ?? [])
          .map((tag) => tag.type?.trim())
          .filter((value): value is string => Boolean(value))
      )
    ).sort((left, right) => left.localeCompare(right));
    const entityCategoryOptions = Array.from(
      new Set(
        (entitiesQuery.data ?? [])
          .map((entity) => entity.category?.trim())
          .filter((value): value is string => Boolean(value))
      )
    ).sort((left, right) => left.localeCompare(right));
    return {
      currencies: currenciesQuery.data ?? [],
      defaultCurrencyCode,
      editorLoadError,
      entities: entitiesQuery.data ?? [],
      entityCategoryOptions,
      tags: tagsQuery.data ?? [],
      tagTypeOptions
    };
  }, [currenciesQuery, entitiesQuery, runtimeSettingsQuery, tagsQuery]);
}

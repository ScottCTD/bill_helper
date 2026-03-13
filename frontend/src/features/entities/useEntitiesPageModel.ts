/**
 * CALLING SPEC:
 * - Purpose: provide the `useEntitiesPageModel` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/features/entities/useEntitiesPageModel.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `useEntitiesPageModel`.
 * - Side effects: client-side state coordination and query wiring.
 */
import { type FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createEntity, deleteEntity, listEntities, listTaxonomyTerms, updateEntity } from "../../lib/api";
import {
  ENTITY_CATEGORY_TAXONOMY_KEY,
  includesFilter,
  taxonomyTermNames,
  uniqueOptionValues
} from "../../lib/catalogs";
import { invalidateEntityReadModels } from "../../lib/queryInvalidation";
import { queryKeys } from "../../lib/queryKeys";
import type { Entity } from "../../lib/types";

function matchesEntitySearch(entity: Entity, search: string) {
  return includesFilter(entity.name, search) || includesFilter(entity.category, search);
}

export function useEntitiesPageModel() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [createPanelOpen, setCreatePanelOpen] = useState(false);
  const [newEntityName, setNewEntityName] = useState("");
  const [newEntityCategory, setNewEntityCategory] = useState("");
  const [editingEntityId, setEditingEntityId] = useState("");
  const [editingEntityName, setEditingEntityName] = useState("");
  const [editingEntityCategory, setEditingEntityCategory] = useState("");
  const [deletingEntityId, setDeletingEntityId] = useState("");

  const entitiesQuery = useQuery({ queryKey: queryKeys.properties.entities, queryFn: listEntities });
  const entityCategoryTermsQuery = useQuery({
    queryKey: queryKeys.properties.taxonomyTerms(ENTITY_CATEGORY_TAXONOMY_KEY),
    queryFn: () => listTaxonomyTerms(ENTITY_CATEGORY_TAXONOMY_KEY)
  });

  const createEntityMutation = useMutation({
    mutationFn: createEntity,
    onSuccess: () => {
      setNewEntityName("");
      setNewEntityCategory("");
      setCreatePanelOpen(false);
      invalidateEntityReadModels(queryClient);
    }
  });

  const updateEntityMutation = useMutation({
    mutationFn: ({ entityId, name, category }: { entityId: string; name: string; category: string }) =>
      updateEntity(entityId, { name, category: category || null }),
    onSuccess: () => {
      setEditingEntityId("");
      setEditingEntityName("");
      setEditingEntityCategory("");
      invalidateEntityReadModels(queryClient);
    }
  });

  const deleteEntityMutation = useMutation({
    mutationFn: deleteEntity,
    onSuccess: (_data, deletedEntityId) => {
      if (editingEntityId === deletedEntityId) {
        setEditingEntityId("");
        setEditingEntityName("");
        setEditingEntityCategory("");
      }
      setDeletingEntityId("");
      invalidateEntityReadModels(queryClient);
    }
  });

  const entityCategoryOptions = useMemo(
    () =>
      uniqueOptionValues([
        ...taxonomyTermNames(entityCategoryTermsQuery.data),
        ...(entitiesQuery.data ?? []).map((entity) => entity.category)
      ]),
    [entitiesQuery.data, entityCategoryTermsQuery.data]
  );

  const filteredEntities = useMemo(
    () => (entitiesQuery.data ?? []).filter((entity) => !entity.is_account && matchesEntitySearch(entity, search)),
    [entitiesQuery.data, search]
  );

  const deletingEntity = useMemo(
    () => (entitiesQuery.data ?? []).find((entity) => entity.id === deletingEntityId) ?? null,
    [deletingEntityId, entitiesQuery.data]
  );

  function closeCreatePanel() {
    setCreatePanelOpen(false);
  }

  function onCreateEntity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newEntityName.trim();
    if (!name) {
      return;
    }
    createEntityMutation.mutate({ name, category: newEntityCategory.trim() || null });
  }

  function saveEntity(entityId: string) {
    const name = editingEntityName.trim();
    if (!name) {
      return;
    }
    updateEntityMutation.mutate({
      entityId,
      name,
      category: editingEntityCategory.trim()
    });
  }

  function startEditEntity(entity: Entity) {
    setEditingEntityId(entity.id);
    setEditingEntityName(entity.name);
    setEditingEntityCategory(entity.category ?? "");
  }

  function cancelEditEntity() {
    setEditingEntityId("");
    setEditingEntityName("");
    setEditingEntityCategory("");
  }

  function startDeleteEntity(entity: Entity) {
    setDeletingEntityId(entity.id);
    deleteEntityMutation.reset();
  }

  function cancelDeleteEntity() {
    setDeletingEntityId("");
    deleteEntityMutation.reset();
  }

  function confirmDeleteEntity() {
    if (!deletingEntityId) {
      return;
    }
    deleteEntityMutation.mutate(deletingEntityId);
  }

  return {
    search,
    setSearch,
    createPanelOpen,
    setCreatePanelOpen,
    closeCreatePanel,
    forms: {
      newEntityName,
      setNewEntityName,
      newEntityCategory,
      setNewEntityCategory,
      editingEntityId,
      editingEntityName,
      setEditingEntityName,
      editingEntityCategory,
      setEditingEntityCategory
    },
    queries: {
      entitiesQuery,
      entityCategoryTermsQuery
    },
    mutations: {
      createEntityMutation,
      updateEntityMutation,
      deleteEntityMutation
    },
    filteredEntities,
    entityCategoryOptions,
    deletingEntity,
    hasAnyEntities: (entitiesQuery.data ?? []).some((entity) => !entity.is_account),
    actions: {
      onCreateEntity,
      saveEntity,
      startEditEntity,
      cancelEditEntity,
      startDeleteEntity,
      cancelDeleteEntity,
      confirmDeleteEntity
    }
  };
}

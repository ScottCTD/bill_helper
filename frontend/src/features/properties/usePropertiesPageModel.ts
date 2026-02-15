import { type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createEntity,
  createTag,
  createTaxonomyTerm,
  createUser,
  updateEntity,
  updateTag,
  updateTaxonomyTerm,
  updateUser
} from "../../lib/api";
import {
  invalidateEntityReadModels,
  invalidateTagReadModels,
  invalidateTaxonomyReadModels,
  invalidateUserReadModels
} from "../../lib/queryInvalidation";
import type { Entity, Tag, TaxonomyTerm, User } from "../../lib/types";
import { ENTITY_CATEGORY_TAXONOMY_KEY, TAG_CATEGORY_TAXONOMY_KEY } from "./types";
import { usePropertiesFilteredData } from "./usePropertiesFilteredData";
import { usePropertiesFormState } from "./usePropertiesFormState";
import { usePropertiesQueries } from "./usePropertiesQueries";
import { usePropertiesSectionState } from "./usePropertiesSectionState";

export function usePropertiesPageModel() {
  const queryClient = useQueryClient();
  const queryState = usePropertiesQueries();
  const sectionState = usePropertiesSectionState();
  const forms = usePropertiesFormState();

  const { queries, options } = queryState;
  const { entityCategoriesLabel, tagCategoriesLabel } = queryState.labels;

  const filtered = usePropertiesFilteredData({
    sectionSearch: sectionState.sectionSearch,
    users: queries.usersQuery.data,
    entities: queries.entitiesQuery.data,
    tags: queries.tagsQuery.data,
    currencies: queries.currenciesQuery.data,
    entityCategoryTerms: queries.entityCategoryTermsQuery.data,
    tagCategoryTerms: queries.tagCategoryTermsQuery.data
  });

  const createEntityMutation = useMutation({
    mutationFn: createEntity,
    onSuccess: () => {
      forms.setNewEntityName("");
      forms.setNewEntityCategory("");
      sectionState.actions.closeCreatePanel("entities");
      invalidateEntityReadModels(queryClient);
    }
  });

  const updateEntityMutation = useMutation({
    mutationFn: ({ entityId, name, category }: { entityId: string; name: string; category: string }) =>
      updateEntity(entityId, { name, category: category || null }),
    onSuccess: () => {
      forms.setEditingEntityId("");
      forms.setEditingEntityName("");
      forms.setEditingEntityCategory("");
      invalidateEntityReadModels(queryClient);
    }
  });

  const createTagMutation = useMutation({
    mutationFn: createTag,
    onSuccess: () => {
      forms.setNewTagName("");
      forms.setNewTagCategory("");
      forms.setNewTagColor("");
      sectionState.actions.closeCreatePanel("tags");
      invalidateTagReadModels(queryClient);
    }
  });

  const updateTagMutation = useMutation({
    mutationFn: ({ tagId, name, color, category }: { tagId: number; name: string; color: string; category: string }) =>
      updateTag(tagId, { name, color: color || null, category: category || null }),
    onSuccess: () => {
      forms.setEditingTagId(null);
      forms.setEditingTagName("");
      forms.setEditingTagCategory("");
      forms.setEditingTagColor("");
      invalidateTagReadModels(queryClient);
    }
  });

  const createUserMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      forms.setNewUserName("");
      sectionState.actions.closeCreatePanel("users");
      invalidateUserReadModels(queryClient);
    }
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ userId, name }: { userId: string; name: string }) => updateUser(userId, { name }),
    onSuccess: () => {
      forms.setEditingUserId("");
      forms.setEditingUserName("");
      invalidateUserReadModels(queryClient);
    }
  });

  const createEntityCategoryTermMutation = useMutation({
    mutationFn: ({ name }: { name: string }) => createTaxonomyTerm(ENTITY_CATEGORY_TAXONOMY_KEY, { name }),
    onSuccess: () => {
      forms.setNewEntityCategoryTermName("");
      sectionState.actions.closeCreatePanel("entityCategories");
      invalidateTaxonomyReadModels(queryClient, ENTITY_CATEGORY_TAXONOMY_KEY);
    }
  });

  const updateEntityCategoryTermMutation = useMutation({
    mutationFn: ({ termId, name }: { termId: string; name: string }) =>
      updateTaxonomyTerm(ENTITY_CATEGORY_TAXONOMY_KEY, termId, { name }),
    onSuccess: () => {
      forms.setEditingEntityCategoryTermId("");
      forms.setEditingEntityCategoryTermName("");
      invalidateTaxonomyReadModels(queryClient, ENTITY_CATEGORY_TAXONOMY_KEY);
    }
  });

  const createTagCategoryTermMutation = useMutation({
    mutationFn: ({ name }: { name: string }) => createTaxonomyTerm(TAG_CATEGORY_TAXONOMY_KEY, { name }),
    onSuccess: () => {
      forms.setNewTagCategoryTermName("");
      sectionState.actions.closeCreatePanel("tagCategories");
      invalidateTaxonomyReadModels(queryClient, TAG_CATEGORY_TAXONOMY_KEY);
    }
  });

  const updateTagCategoryTermMutation = useMutation({
    mutationFn: ({ termId, name }: { termId: string; name: string }) => updateTaxonomyTerm(TAG_CATEGORY_TAXONOMY_KEY, termId, { name }),
    onSuccess: () => {
      forms.setEditingTagCategoryTermId("");
      forms.setEditingTagCategoryTermName("");
      invalidateTaxonomyReadModels(queryClient, TAG_CATEGORY_TAXONOMY_KEY);
    }
  });

  function onCreateEntity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = forms.newEntityName.trim();
    if (!name) {
      return;
    }
    createEntityMutation.mutate({ name, category: forms.newEntityCategory.trim() || null });
  }

  function onCreateTag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = forms.newTagName.trim();
    if (!name) {
      return;
    }
    createTagMutation.mutate({
      name,
      category: forms.newTagCategory.trim() || undefined,
      color: forms.newTagColor.trim() || undefined
    });
  }

  function onCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = forms.newUserName.trim();
    if (!name) {
      return;
    }
    createUserMutation.mutate({ name });
  }

  function onCreateEntityCategoryTerm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = forms.newEntityCategoryTermName.trim();
    if (!name) {
      return;
    }
    createEntityCategoryTermMutation.mutate({ name });
  }

  function onCreateTagCategoryTerm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = forms.newTagCategoryTermName.trim();
    if (!name) {
      return;
    }
    createTagCategoryTermMutation.mutate({ name });
  }

  function saveUser(userId: string) {
    const name = forms.editingUserName.trim();
    if (!name) {
      return;
    }
    updateUserMutation.mutate({ userId, name });
  }

  function startEditUser(user: User) {
    forms.setEditingUserId(user.id);
    forms.setEditingUserName(user.name);
  }

  function cancelEditUser() {
    forms.setEditingUserId("");
    forms.setEditingUserName("");
  }

  function saveEntity(entityId: string) {
    const name = forms.editingEntityName.trim();
    if (!name) {
      return;
    }
    updateEntityMutation.mutate({
      entityId,
      name,
      category: forms.editingEntityCategory.trim()
    });
  }

  function startEditEntity(entity: Entity) {
    forms.setEditingEntityId(entity.id);
    forms.setEditingEntityName(entity.name);
    forms.setEditingEntityCategory(entity.category ?? "");
  }

  function cancelEditEntity() {
    forms.setEditingEntityId("");
    forms.setEditingEntityName("");
    forms.setEditingEntityCategory("");
  }

  function saveTag(tagId: number) {
    const name = forms.editingTagName.trim();
    if (!name) {
      return;
    }
    updateTagMutation.mutate({
      tagId,
      name,
      color: forms.editingTagColor.trim(),
      category: forms.editingTagCategory.trim()
    });
  }

  function startEditTag(tag: Tag) {
    forms.setEditingTagId(tag.id);
    forms.setEditingTagName(tag.name);
    forms.setEditingTagCategory(tag.category ?? "");
    forms.setEditingTagColor(tag.color ?? "");
  }

  function cancelEditTag() {
    forms.setEditingTagId(null);
    forms.setEditingTagName("");
    forms.setEditingTagCategory("");
    forms.setEditingTagColor("");
  }

  function saveEntityCategoryTerm(termId: string) {
    const name = forms.editingEntityCategoryTermName.trim();
    if (!name) {
      return;
    }
    updateEntityCategoryTermMutation.mutate({ termId, name });
  }

  function startEditEntityCategoryTerm(term: TaxonomyTerm) {
    forms.setEditingEntityCategoryTermId(term.id);
    forms.setEditingEntityCategoryTermName(term.name);
  }

  function cancelEditEntityCategoryTerm() {
    forms.setEditingEntityCategoryTermId("");
    forms.setEditingEntityCategoryTermName("");
  }

  function saveTagCategoryTerm(termId: string) {
    const name = forms.editingTagCategoryTermName.trim();
    if (!name) {
      return;
    }
    updateTagCategoryTermMutation.mutate({ termId, name });
  }

  function startEditTagCategoryTerm(term: TaxonomyTerm) {
    forms.setEditingTagCategoryTermId(term.id);
    forms.setEditingTagCategoryTermName(term.name);
  }

  function cancelEditTagCategoryTerm() {
    forms.setEditingTagCategoryTermId("");
    forms.setEditingTagCategoryTermName("");
  }

  const coreSections = [
    { id: "users" as const, label: "Users" },
    { id: "entities" as const, label: "Entities" },
    { id: "tags" as const, label: "Tags" },
    { id: "currencies" as const, label: "Currencies" }
  ];

  const taxonomySections = [
    { id: "entityCategories" as const, label: entityCategoriesLabel },
    { id: "tagCategories" as const, label: tagCategoriesLabel }
  ];

  return {
    activeSection: sectionState.activeSection,
    setActiveSection: sectionState.setActiveSection,
    sectionSearch: sectionState.sectionSearch,
    createPanelOpen: sectionState.createPanelOpen,
    coreSections,
    taxonomySections,
    entityCategoriesLabel,
    tagCategoriesLabel,
    queries,
    filtered,
    options,
    forms: {
      newEntityName: forms.newEntityName,
      setNewEntityName: forms.setNewEntityName,
      newEntityCategory: forms.newEntityCategory,
      setNewEntityCategory: forms.setNewEntityCategory,
      editingEntityId: forms.editingEntityId,
      editingEntityName: forms.editingEntityName,
      setEditingEntityName: forms.setEditingEntityName,
      editingEntityCategory: forms.editingEntityCategory,
      setEditingEntityCategory: forms.setEditingEntityCategory,
      newTagName: forms.newTagName,
      setNewTagName: forms.setNewTagName,
      newTagCategory: forms.newTagCategory,
      setNewTagCategory: forms.setNewTagCategory,
      newTagColor: forms.newTagColor,
      setNewTagColor: forms.setNewTagColor,
      editingTagId: forms.editingTagId,
      editingTagName: forms.editingTagName,
      setEditingTagName: forms.setEditingTagName,
      editingTagCategory: forms.editingTagCategory,
      setEditingTagCategory: forms.setEditingTagCategory,
      editingTagColor: forms.editingTagColor,
      setEditingTagColor: forms.setEditingTagColor,
      newUserName: forms.newUserName,
      setNewUserName: forms.setNewUserName,
      editingUserId: forms.editingUserId,
      editingUserName: forms.editingUserName,
      setEditingUserName: forms.setEditingUserName,
      newEntityCategoryTermName: forms.newEntityCategoryTermName,
      setNewEntityCategoryTermName: forms.setNewEntityCategoryTermName,
      editingEntityCategoryTermId: forms.editingEntityCategoryTermId,
      editingEntityCategoryTermName: forms.editingEntityCategoryTermName,
      setEditingEntityCategoryTermName: forms.setEditingEntityCategoryTermName,
      newTagCategoryTermName: forms.newTagCategoryTermName,
      setNewTagCategoryTermName: forms.setNewTagCategoryTermName,
      editingTagCategoryTermId: forms.editingTagCategoryTermId,
      editingTagCategoryTermName: forms.editingTagCategoryTermName,
      setEditingTagCategoryTermName: forms.setEditingTagCategoryTermName
    },
    actions: {
      setSectionSearchValue: sectionState.actions.setSectionSearchValue,
      toggleCreatePanel: sectionState.actions.toggleCreatePanel,
      closeCreatePanel: sectionState.actions.closeCreatePanel,
      onCreateEntity,
      onCreateTag,
      onCreateUser,
      onCreateEntityCategoryTerm,
      onCreateTagCategoryTerm,
      saveUser,
      startEditUser,
      cancelEditUser,
      saveEntity,
      startEditEntity,
      cancelEditEntity,
      saveTag,
      startEditTag,
      cancelEditTag,
      saveEntityCategoryTerm,
      startEditEntityCategoryTerm,
      cancelEditEntityCategoryTerm,
      saveTagCategoryTerm,
      startEditTagCategoryTerm,
      cancelEditTagCategoryTerm
    },
    mutations: {
      createEntityMutation,
      updateEntityMutation,
      createTagMutation,
      updateTagMutation,
      createUserMutation,
      updateUserMutation,
      createEntityCategoryTermMutation,
      updateEntityCategoryTermMutation,
      createTagCategoryTermMutation,
      updateTagCategoryTermMutation
    }
  };
}

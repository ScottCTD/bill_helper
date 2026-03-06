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
import { ENTITY_CATEGORY_TAXONOMY_KEY, TAG_TYPE_TAXONOMY_KEY } from "./types";
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
  const { entityCategoriesLabel, tagTypesLabel } = queryState.labels;

  const filtered = usePropertiesFilteredData({
    sectionSearch: sectionState.sectionSearch,
    users: queries.usersQuery.data,
    entities: queries.entitiesQuery.data,
    tags: queries.tagsQuery.data,
    currencies: queries.currenciesQuery.data,
    entityCategoryTerms: queries.entityCategoryTermsQuery.data,
    tagTypeTerms: queries.tagTypeTermsQuery.data
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
      forms.setNewTagType("");
      forms.setNewTagColor("");
      forms.setNewTagDescription("");
      sectionState.actions.closeCreatePanel("tags");
      invalidateTagReadModels(queryClient);
    }
  });

  const updateTagMutation = useMutation({
    mutationFn: ({
      tagId,
      name,
      color,
      description,
      type
    }: {
      tagId: number;
      name: string;
      color: string;
      description: string;
      type: string;
    }) => updateTag(tagId, { name, color: color || null, description: description || null, type: type || null }),
    onSuccess: () => {
      forms.setEditingTagId(null);
      forms.setEditingTagName("");
      forms.setEditingTagType("");
      forms.setEditingTagColor("");
      forms.setEditingTagDescription("");
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
    mutationFn: ({ name, description }: { name: string; description?: string }) =>
      createTaxonomyTerm(ENTITY_CATEGORY_TAXONOMY_KEY, { name, description }),
    onSuccess: () => {
      forms.setNewEntityCategoryTermName("");
      forms.setNewEntityCategoryTermDescription("");
      sectionState.actions.closeCreatePanel("entityCategories");
      invalidateTaxonomyReadModels(queryClient, ENTITY_CATEGORY_TAXONOMY_KEY);
    }
  });

  const updateEntityCategoryTermMutation = useMutation({
    mutationFn: ({ termId, name, description }: { termId: string; name: string; description?: string | null }) =>
      updateTaxonomyTerm(ENTITY_CATEGORY_TAXONOMY_KEY, termId, { name, description }),
    onSuccess: () => {
      forms.setEditingEntityCategoryTermId("");
      forms.setEditingEntityCategoryTermName("");
      forms.setEditingEntityCategoryTermDescription("");
      invalidateTaxonomyReadModels(queryClient, ENTITY_CATEGORY_TAXONOMY_KEY);
    }
  });

  const createTagTypeTermMutation = useMutation({
    mutationFn: ({ name, description }: { name: string; description?: string }) =>
      createTaxonomyTerm(TAG_TYPE_TAXONOMY_KEY, { name, description }),
    onSuccess: () => {
      forms.setNewTagTypeTermName("");
      forms.setNewTagTypeTermDescription("");
      sectionState.actions.closeCreatePanel("tagCategories");
      invalidateTaxonomyReadModels(queryClient, TAG_TYPE_TAXONOMY_KEY);
    }
  });

  const updateTagTypeTermMutation = useMutation({
    mutationFn: ({ termId, name, description }: { termId: string; name: string; description?: string | null }) =>
      updateTaxonomyTerm(TAG_TYPE_TAXONOMY_KEY, termId, { name, description }),
    onSuccess: () => {
      forms.setEditingTagTypeTermId("");
      forms.setEditingTagTypeTermName("");
      forms.setEditingTagTypeTermDescription("");
      invalidateTaxonomyReadModels(queryClient, TAG_TYPE_TAXONOMY_KEY);
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
      type: forms.newTagType.trim() || undefined,
      color: forms.newTagColor.trim() || undefined,
      description: forms.newTagDescription.trim() || undefined
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
    createEntityCategoryTermMutation.mutate({
      name,
      description: forms.newEntityCategoryTermDescription.trim() || undefined
    });
  }

  function onCreateTagTypeTerm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = forms.newTagTypeTermName.trim();
    if (!name) {
      return;
    }
    createTagTypeTermMutation.mutate({
      name,
      description: forms.newTagTypeTermDescription.trim() || undefined
    });
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
      description: forms.editingTagDescription.trim(),
      type: forms.editingTagType.trim()
    });
  }

  function startEditTag(tag: Tag) {
    forms.setEditingTagId(tag.id);
    forms.setEditingTagName(tag.name);
    forms.setEditingTagType(tag.type ?? "");
    forms.setEditingTagColor(tag.color ?? "");
    forms.setEditingTagDescription(tag.description ?? "");
  }

  function cancelEditTag() {
    forms.setEditingTagId(null);
    forms.setEditingTagName("");
    forms.setEditingTagType("");
    forms.setEditingTagColor("");
    forms.setEditingTagDescription("");
  }

  function saveEntityCategoryTerm(termId: string) {
    const name = forms.editingEntityCategoryTermName.trim();
    if (!name) {
      return;
    }
    updateEntityCategoryTermMutation.mutate({
      termId,
      name,
      description: forms.editingEntityCategoryTermDescription.trim() || null
    });
  }

  function startEditEntityCategoryTerm(term: TaxonomyTerm) {
    forms.setEditingEntityCategoryTermId(term.id);
    forms.setEditingEntityCategoryTermName(term.name);
    forms.setEditingEntityCategoryTermDescription(term.description ?? "");
  }

  function cancelEditEntityCategoryTerm() {
    forms.setEditingEntityCategoryTermId("");
    forms.setEditingEntityCategoryTermName("");
    forms.setEditingEntityCategoryTermDescription("");
  }

  function saveTagTypeTerm(termId: string) {
    const name = forms.editingTagTypeTermName.trim();
    if (!name) {
      return;
    }
    updateTagTypeTermMutation.mutate({
      termId,
      name,
      description: forms.editingTagTypeTermDescription.trim() || null
    });
  }

  function startEditTagTypeTerm(term: TaxonomyTerm) {
    forms.setEditingTagTypeTermId(term.id);
    forms.setEditingTagTypeTermName(term.name);
    forms.setEditingTagTypeTermDescription(term.description ?? "");
  }

  function cancelEditTagTypeTerm() {
    forms.setEditingTagTypeTermId("");
    forms.setEditingTagTypeTermName("");
    forms.setEditingTagTypeTermDescription("");
  }

  const coreSections = [
    { id: "users" as const, label: "Users" },
    { id: "entities" as const, label: "Entities" },
    { id: "tags" as const, label: "Tags" },
    { id: "currencies" as const, label: "Currencies" }
  ];

  const taxonomySections = [
    { id: "entityCategories" as const, label: entityCategoriesLabel },
    { id: "tagCategories" as const, label: tagTypesLabel }
  ];

  return {
    activeSection: sectionState.activeSection,
    setActiveSection: sectionState.setActiveSection,
    sectionSearch: sectionState.sectionSearch,
    createPanelOpen: sectionState.createPanelOpen,
    coreSections,
    taxonomySections,
    entityCategoriesLabel,
    tagTypesLabel,
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
      newTagType: forms.newTagType,
      setNewTagType: forms.setNewTagType,
      newTagColor: forms.newTagColor,
      setNewTagColor: forms.setNewTagColor,
      newTagDescription: forms.newTagDescription,
      setNewTagDescription: forms.setNewTagDescription,
      editingTagId: forms.editingTagId,
      editingTagName: forms.editingTagName,
      setEditingTagName: forms.setEditingTagName,
      editingTagType: forms.editingTagType,
      setEditingTagType: forms.setEditingTagType,
      editingTagColor: forms.editingTagColor,
      setEditingTagColor: forms.setEditingTagColor,
      editingTagDescription: forms.editingTagDescription,
      setEditingTagDescription: forms.setEditingTagDescription,
      newUserName: forms.newUserName,
      setNewUserName: forms.setNewUserName,
      editingUserId: forms.editingUserId,
      editingUserName: forms.editingUserName,
      setEditingUserName: forms.setEditingUserName,
      newEntityCategoryTermName: forms.newEntityCategoryTermName,
      setNewEntityCategoryTermName: forms.setNewEntityCategoryTermName,
      newEntityCategoryTermDescription: forms.newEntityCategoryTermDescription,
      setNewEntityCategoryTermDescription: forms.setNewEntityCategoryTermDescription,
      editingEntityCategoryTermId: forms.editingEntityCategoryTermId,
      editingEntityCategoryTermName: forms.editingEntityCategoryTermName,
      setEditingEntityCategoryTermName: forms.setEditingEntityCategoryTermName,
      editingEntityCategoryTermDescription: forms.editingEntityCategoryTermDescription,
      setEditingEntityCategoryTermDescription: forms.setEditingEntityCategoryTermDescription,
      newTagTypeTermName: forms.newTagTypeTermName,
      setNewTagTypeTermName: forms.setNewTagTypeTermName,
      newTagTypeTermDescription: forms.newTagTypeTermDescription,
      setNewTagTypeTermDescription: forms.setNewTagTypeTermDescription,
      editingTagTypeTermId: forms.editingTagTypeTermId,
      editingTagTypeTermName: forms.editingTagTypeTermName,
      setEditingTagTypeTermName: forms.setEditingTagTypeTermName,
      editingTagTypeTermDescription: forms.editingTagTypeTermDescription,
      setEditingTagTypeTermDescription: forms.setEditingTagTypeTermDescription
    },
    actions: {
      setSectionSearchValue: sectionState.actions.setSectionSearchValue,
      toggleCreatePanel: sectionState.actions.toggleCreatePanel,
      closeCreatePanel: sectionState.actions.closeCreatePanel,
      onCreateEntity,
      onCreateTag,
      onCreateUser,
      onCreateEntityCategoryTerm,
      onCreateTagTypeTerm,
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
      saveTagTypeTerm,
      startEditTagTypeTerm,
      cancelEditTagTypeTerm
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
      createTagTypeTermMutation,
      updateTagTypeTermMutation
    }
  };
}

export type PropertiesPageModel = ReturnType<typeof usePropertiesPageModel>;

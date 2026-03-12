import { type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createTag,
  createTaxonomyTerm,
  deleteTag,
  updateTag,
  updateTaxonomyTerm
} from "../../lib/api";
import { ENTITY_CATEGORY_TAXONOMY_KEY, TAG_TYPE_TAXONOMY_KEY } from "../../lib/catalogs";
import { invalidateTagReadModels, invalidateTaxonomyReadModels } from "../../lib/queryInvalidation";
import type { Tag, TaxonomyTerm } from "../../lib/types";
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
  const deletingTag = (queries.tagsQuery.data ?? []).find((tag) => tag.id === forms.deletingTagId) ?? null;

  const filtered = usePropertiesFilteredData({
    sectionSearch: sectionState.sectionSearch,
    tags: queries.tagsQuery.data,
    currencies: queries.currenciesQuery.data,
    entityCategoryTerms: queries.entityCategoryTermsQuery.data,
    tagTypeTerms: queries.tagTypeTermsQuery.data
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

  const deleteTagMutation = useMutation({
    mutationFn: deleteTag,
    onSuccess: (_data, deletedTagId) => {
      if (forms.editingTagId === deletedTagId) {
        forms.setEditingTagId(null);
        forms.setEditingTagName("");
        forms.setEditingTagType("");
        forms.setEditingTagColor("");
        forms.setEditingTagDescription("");
      }
      forms.setDeletingTagId(null);
      invalidateTagReadModels(queryClient);
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

  function startDeleteTag(tag: Tag) {
    forms.setDeletingTagId(tag.id);
    deleteTagMutation.reset();
  }

  function cancelDeleteTag() {
    forms.setDeletingTagId(null);
    deleteTagMutation.reset();
  }

  function confirmDeleteTag() {
    if (forms.deletingTagId === null) {
      return;
    }
    deleteTagMutation.mutate(forms.deletingTagId);
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
      deletingTagId: forms.deletingTagId,
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
      onCreateTag,
      onCreateEntityCategoryTerm,
      onCreateTagTypeTerm,
      saveTag,
      startEditTag,
      cancelEditTag,
      startDeleteTag,
      cancelDeleteTag,
      confirmDeleteTag,
      saveEntityCategoryTerm,
      startEditEntityCategoryTerm,
      cancelEditEntityCategoryTerm,
      saveTagTypeTerm,
      startEditTagTypeTerm,
      cancelEditTagTypeTerm
    },
    mutations: {
      createTagMutation,
      updateTagMutation,
      deleteTagMutation,
      createEntityCategoryTermMutation,
      updateEntityCategoryTermMutation,
      createTagTypeTermMutation,
      updateTagTypeTermMutation
    },
    deleteTargets: {
      tag: deletingTag
    }
  };
}

export type PropertiesPageModel = ReturnType<typeof usePropertiesPageModel>;

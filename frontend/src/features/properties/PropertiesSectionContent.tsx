/**
 * CALLING SPEC:
 * - Purpose: render the `PropertiesSectionContent` React UI module.
 * - Inputs: callers that import `frontend/src/features/properties/PropertiesSectionContent.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `PropertiesSectionContent`.
 * - Side effects: React rendering and user event wiring.
 */
import { CurrenciesSection } from "./sections/CurrenciesSection";
import { TagsSection } from "./sections/TagsSection";
import { TaxonomyTermsSection } from "./sections/TaxonomyTermsSection";
import type { PropertiesPageModel } from "./usePropertiesPageModel";

interface PropertiesSectionContentProps {
  model: PropertiesPageModel;
}

function queryErrorMessage(error: unknown): string | null {
  return error instanceof Error ? error.message : null;
}

export function PropertiesSectionContent({ model }: PropertiesSectionContentProps) {
  switch (model.activeSection) {
    case "tags":
      return (
        <TagsSection
          search={model.sectionSearch.tags}
          onSearchChange={(value) => model.actions.setSectionSearchValue("tags", value)}
          createPanelOpen={model.createPanelOpen.tags}
          onToggleCreatePanel={() => model.actions.toggleCreatePanel("tags")}
          onCloseCreatePanel={() => model.actions.closeCreatePanel("tags")}
          newTagName={model.forms.newTagName}
          onNewTagNameChange={model.forms.setNewTagName}
          newTagType={model.forms.newTagType}
          onNewTagTypeChange={model.forms.setNewTagType}
          newTagColor={model.forms.newTagColor}
          onNewTagColorChange={model.forms.setNewTagColor}
          newTagDescription={model.forms.newTagDescription}
          onNewTagDescriptionChange={model.forms.setNewTagDescription}
          editingTagId={model.forms.editingTagId}
          editingTagName={model.forms.editingTagName}
          onEditingTagNameChange={model.forms.setEditingTagName}
          editingTagType={model.forms.editingTagType}
          onEditingTagTypeChange={model.forms.setEditingTagType}
          editingTagColor={model.forms.editingTagColor}
          onEditingTagColorChange={model.forms.setEditingTagColor}
          editingTagDescription={model.forms.editingTagDescription}
          onEditingTagDescriptionChange={model.forms.setEditingTagDescription}
          onStartEditTag={model.actions.startEditTag}
          onCancelEditTag={model.actions.cancelEditTag}
          onSaveTag={model.actions.saveTag}
          onStartDeleteTag={model.actions.startDeleteTag}
          onCancelDeleteTag={model.actions.cancelDeleteTag}
          onConfirmDeleteTag={model.actions.confirmDeleteTag}
          onCreateTagSubmit={model.actions.onCreateTag}
          tags={model.filtered.tags}
          deletingTag={model.deleteTargets.tag}
          hasAnyTags={(model.queries.tagsQuery.data ?? []).length > 0}
          tagTypeOptions={model.options.tagTypeOptions}
          isLoading={model.queries.tagsQuery.isLoading}
          isError={model.queries.tagsQuery.isError}
          queryErrorMessage={queryErrorMessage(model.queries.tagsQuery.error)}
          createErrorMessage={queryErrorMessage(model.mutations.createTagMutation.error)}
          updateErrorMessage={queryErrorMessage(model.mutations.updateTagMutation.error)}
          deleteErrorMessage={queryErrorMessage(model.mutations.deleteTagMutation.error)}
          isCreating={model.mutations.createTagMutation.isPending}
          isUpdating={model.mutations.updateTagMutation.isPending}
          isDeleting={model.mutations.deleteTagMutation.isPending}
        />
      );
    case "currencies":
      return (
        <CurrenciesSection
          search={model.sectionSearch.currencies}
          onSearchChange={(value) => model.actions.setSectionSearchValue("currencies", value)}
          currencies={model.filtered.currencies}
          hasAnyCurrencies={(model.queries.currenciesQuery.data ?? []).length > 0}
          isLoading={model.queries.currenciesQuery.isLoading}
          isError={model.queries.currenciesQuery.isError}
          queryErrorMessage={queryErrorMessage(model.queries.currenciesQuery.error)}
        />
      );
    case "entityCategories":
      return (
        <TaxonomyTermsSection
          label={model.entityCategoriesLabel}
          search={model.sectionSearch.entityCategories}
          onSearchChange={(value) => model.actions.setSectionSearchValue("entityCategories", value)}
          createPanelOpen={model.createPanelOpen.entityCategories}
          onToggleCreatePanel={() => model.actions.toggleCreatePanel("entityCategories")}
          onCloseCreatePanel={() => model.actions.closeCreatePanel("entityCategories")}
          newTermName={model.forms.newEntityCategoryTermName}
          onNewTermNameChange={model.forms.setNewEntityCategoryTermName}
          newTermDescription={model.forms.newEntityCategoryTermDescription}
          onNewTermDescriptionChange={model.forms.setNewEntityCategoryTermDescription}
          editingTermId={model.forms.editingEntityCategoryTermId}
          editingTermName={model.forms.editingEntityCategoryTermName}
          onEditingTermNameChange={model.forms.setEditingEntityCategoryTermName}
          editingTermDescription={model.forms.editingEntityCategoryTermDescription}
          onEditingTermDescriptionChange={model.forms.setEditingEntityCategoryTermDescription}
          onStartEditTerm={model.actions.startEditEntityCategoryTerm}
          onCancelEditTerm={model.actions.cancelEditEntityCategoryTerm}
          onSaveTerm={model.actions.saveEntityCategoryTerm}
          onCreateTermSubmit={model.actions.onCreateEntityCategoryTerm}
          terms={model.filtered.entityCategoryTerms}
          hasAnyTerms={(model.queries.entityCategoryTermsQuery.data ?? []).length > 0}
          isLoading={model.queries.entityCategoryTermsQuery.isLoading}
          isError={model.queries.entityCategoryTermsQuery.isError}
          queryErrorMessage={queryErrorMessage(model.queries.entityCategoryTermsQuery.error)}
          createErrorMessage={queryErrorMessage(model.mutations.createEntityCategoryTermMutation.error)}
          updateErrorMessage={queryErrorMessage(model.mutations.updateEntityCategoryTermMutation.error)}
          isCreating={model.mutations.createEntityCategoryTermMutation.isPending}
          isUpdating={model.mutations.updateEntityCategoryTermMutation.isPending}
        />
      );
    case "tagCategories":
      return (
        <TaxonomyTermsSection
          label={model.tagTypesLabel}
          search={model.sectionSearch.tagCategories}
          onSearchChange={(value) => model.actions.setSectionSearchValue("tagCategories", value)}
          createPanelOpen={model.createPanelOpen.tagCategories}
          onToggleCreatePanel={() => model.actions.toggleCreatePanel("tagCategories")}
          onCloseCreatePanel={() => model.actions.closeCreatePanel("tagCategories")}
          newTermName={model.forms.newTagTypeTermName}
          onNewTermNameChange={model.forms.setNewTagTypeTermName}
          newTermDescription={model.forms.newTagTypeTermDescription}
          onNewTermDescriptionChange={model.forms.setNewTagTypeTermDescription}
          editingTermId={model.forms.editingTagTypeTermId}
          editingTermName={model.forms.editingTagTypeTermName}
          onEditingTermNameChange={model.forms.setEditingTagTypeTermName}
          editingTermDescription={model.forms.editingTagTypeTermDescription}
          onEditingTermDescriptionChange={model.forms.setEditingTagTypeTermDescription}
          onStartEditTerm={model.actions.startEditTagTypeTerm}
          onCancelEditTerm={model.actions.cancelEditTagTypeTerm}
          onSaveTerm={model.actions.saveTagTypeTerm}
          onCreateTermSubmit={model.actions.onCreateTagTypeTerm}
          terms={model.filtered.tagTypeTerms}
          hasAnyTerms={(model.queries.tagTypeTermsQuery.data ?? []).length > 0}
          isLoading={model.queries.tagTypeTermsQuery.isLoading}
          isError={model.queries.tagTypeTermsQuery.isError}
          queryErrorMessage={queryErrorMessage(model.queries.tagTypeTermsQuery.error)}
          createErrorMessage={queryErrorMessage(model.mutations.createTagTypeTermMutation.error)}
          updateErrorMessage={queryErrorMessage(model.mutations.updateTagTypeTermMutation.error)}
          isCreating={model.mutations.createTagTypeTermMutation.isPending}
          isUpdating={model.mutations.updateTagTypeTermMutation.isPending}
        />
      );
  }
}

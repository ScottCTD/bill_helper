import type { ReactNode } from "react";

import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { CurrenciesSection } from "../features/properties/sections/CurrenciesSection";
import { EntitiesSection } from "../features/properties/sections/EntitiesSection";
import { TagsSection } from "../features/properties/sections/TagsSection";
import { TaxonomyTermsSection } from "../features/properties/sections/TaxonomyTermsSection";
import { UsersSection } from "../features/properties/sections/UsersSection";
import { usePropertiesPageModel } from "../features/properties/usePropertiesPageModel";

export function PropertiesPage() {
  const model = usePropertiesPageModel();

  let activeSectionContent: ReactNode = null;

  if (model.activeSection === "users") {
    activeSectionContent = (
      <UsersSection
        search={model.sectionSearch.users}
        onSearchChange={(value) => model.actions.setSectionSearchValue("users", value)}
        createPanelOpen={model.createPanelOpen.users}
        onToggleCreatePanel={() => model.actions.toggleCreatePanel("users")}
        onCloseCreatePanel={() => model.actions.closeCreatePanel("users")}
        newUserName={model.forms.newUserName}
        onNewUserNameChange={model.forms.setNewUserName}
        editingUserId={model.forms.editingUserId}
        editingUserName={model.forms.editingUserName}
        onEditingUserNameChange={model.forms.setEditingUserName}
        onStartEditUser={model.actions.startEditUser}
        onCancelEditUser={model.actions.cancelEditUser}
        onSaveUser={model.actions.saveUser}
        onCreateUserSubmit={model.actions.onCreateUser}
        users={model.filtered.users}
        hasAnyUsers={(model.queries.usersQuery.data ?? []).length > 0}
        isLoading={model.queries.usersQuery.isLoading}
        isError={model.queries.usersQuery.isError}
        queryErrorMessage={model.queries.usersQuery.isError ? (model.queries.usersQuery.error as Error).message : null}
        createErrorMessage={model.mutations.createUserMutation.error ? (model.mutations.createUserMutation.error as Error).message : null}
        updateErrorMessage={model.mutations.updateUserMutation.error ? (model.mutations.updateUserMutation.error as Error).message : null}
        isCreating={model.mutations.createUserMutation.isPending}
        isUpdating={model.mutations.updateUserMutation.isPending}
      />
    );
  }

  if (model.activeSection === "entities") {
    activeSectionContent = (
      <EntitiesSection
        search={model.sectionSearch.entities}
        onSearchChange={(value) => model.actions.setSectionSearchValue("entities", value)}
        createPanelOpen={model.createPanelOpen.entities}
        onToggleCreatePanel={() => model.actions.toggleCreatePanel("entities")}
        onCloseCreatePanel={() => model.actions.closeCreatePanel("entities")}
        newEntityName={model.forms.newEntityName}
        onNewEntityNameChange={model.forms.setNewEntityName}
        newEntityCategory={model.forms.newEntityCategory}
        onNewEntityCategoryChange={model.forms.setNewEntityCategory}
        editingEntityId={model.forms.editingEntityId}
        editingEntityName={model.forms.editingEntityName}
        onEditingEntityNameChange={model.forms.setEditingEntityName}
        editingEntityCategory={model.forms.editingEntityCategory}
        onEditingEntityCategoryChange={model.forms.setEditingEntityCategory}
        onStartEditEntity={model.actions.startEditEntity}
        onCancelEditEntity={model.actions.cancelEditEntity}
        onSaveEntity={model.actions.saveEntity}
        onCreateEntitySubmit={model.actions.onCreateEntity}
        entities={model.filtered.entities}
        hasAnyEntities={(model.queries.entitiesQuery.data ?? []).length > 0}
        entityCategoryOptions={model.options.entityCategoryOptions}
        isLoading={model.queries.entitiesQuery.isLoading}
        isError={model.queries.entitiesQuery.isError}
        queryErrorMessage={model.queries.entitiesQuery.isError ? (model.queries.entitiesQuery.error as Error).message : null}
        createErrorMessage={model.mutations.createEntityMutation.error ? (model.mutations.createEntityMutation.error as Error).message : null}
        updateErrorMessage={model.mutations.updateEntityMutation.error ? (model.mutations.updateEntityMutation.error as Error).message : null}
        isCreating={model.mutations.createEntityMutation.isPending}
        isUpdating={model.mutations.updateEntityMutation.isPending}
      />
    );
  }

  if (model.activeSection === "tags") {
    activeSectionContent = (
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
        onCreateTagSubmit={model.actions.onCreateTag}
        tags={model.filtered.tags}
        hasAnyTags={(model.queries.tagsQuery.data ?? []).length > 0}
        tagTypeOptions={model.options.tagTypeOptions}
        isLoading={model.queries.tagsQuery.isLoading}
        isError={model.queries.tagsQuery.isError}
        queryErrorMessage={model.queries.tagsQuery.isError ? (model.queries.tagsQuery.error as Error).message : null}
        createErrorMessage={model.mutations.createTagMutation.error ? (model.mutations.createTagMutation.error as Error).message : null}
        updateErrorMessage={model.mutations.updateTagMutation.error ? (model.mutations.updateTagMutation.error as Error).message : null}
        isCreating={model.mutations.createTagMutation.isPending}
        isUpdating={model.mutations.updateTagMutation.isPending}
      />
    );
  }

  if (model.activeSection === "currencies") {
    activeSectionContent = (
      <CurrenciesSection
        search={model.sectionSearch.currencies}
        onSearchChange={(value) => model.actions.setSectionSearchValue("currencies", value)}
        currencies={model.filtered.currencies}
        hasAnyCurrencies={(model.queries.currenciesQuery.data ?? []).length > 0}
        isLoading={model.queries.currenciesQuery.isLoading}
        isError={model.queries.currenciesQuery.isError}
        queryErrorMessage={model.queries.currenciesQuery.isError ? (model.queries.currenciesQuery.error as Error).message : null}
      />
    );
  }

  if (model.activeSection === "entityCategories") {
    activeSectionContent = (
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
        queryErrorMessage={
          model.queries.entityCategoryTermsQuery.isError ? (model.queries.entityCategoryTermsQuery.error as Error).message : null
        }
        createErrorMessage={
          model.mutations.createEntityCategoryTermMutation.error
            ? (model.mutations.createEntityCategoryTermMutation.error as Error).message
            : null
        }
        updateErrorMessage={
          model.mutations.updateEntityCategoryTermMutation.error
            ? (model.mutations.updateEntityCategoryTermMutation.error as Error).message
            : null
        }
        isCreating={model.mutations.createEntityCategoryTermMutation.isPending}
        isUpdating={model.mutations.updateEntityCategoryTermMutation.isPending}
      />
    );
  }

  if (model.activeSection === "tagCategories") {
    activeSectionContent = (
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
        queryErrorMessage={model.queries.tagTypeTermsQuery.isError ? (model.queries.tagTypeTermsQuery.error as Error).message : null}
        createErrorMessage={
          model.mutations.createTagTypeTermMutation.error
            ? (model.mutations.createTagTypeTermMutation.error as Error).message
            : null
        }
        updateErrorMessage={
          model.mutations.updateTagTypeTermMutation.error
            ? (model.mutations.updateTagTypeTermMutation.error as Error).message
            : null
        }
        isCreating={model.mutations.createTagTypeTermMutation.isPending}
        isUpdating={model.mutations.updateTagTypeTermMutation.isPending}
      />
    );
  }

  return (
    <div className="stack-lg">
      <Card>
        <CardContent className="space-y-5 pt-6">
          <div className="space-y-1.5">
            <h2 className="text-xl font-semibold">Property Databases</h2>
            <p className="muted">
              Manage core catalogs and taxonomy terms from one workspace. Category pickers for entities and type pickers for tags
              are driven by taxonomy terms.
            </p>
            {model.queries.taxonomiesQuery.isError ? <p className="error">{(model.queries.taxonomiesQuery.error as Error).message}</p> : null}
          </div>

          <div className="properties-layout">
            <nav className="properties-nav" aria-label="Property sections">
              <section className="properties-nav-group">
                <p className="properties-nav-label">Core</p>
                <div className="properties-nav-list">
                  {model.coreSections.map((section) => (
                    <Button
                      key={section.id}
                      type="button"
                      size="sm"
                      variant={model.activeSection === section.id ? "secondary" : "ghost"}
                      className="properties-nav-button"
                      onClick={() => model.setActiveSection(section.id)}
                    >
                      {section.label}
                    </Button>
                  ))}
                </div>
              </section>

              <section className="properties-nav-group">
                <p className="properties-nav-label">Taxonomies</p>
                <div className="properties-nav-list">
                  {model.taxonomySections.map((section) => (
                    <Button
                      key={section.id}
                      type="button"
                      size="sm"
                      variant={model.activeSection === section.id ? "secondary" : "ghost"}
                      className="properties-nav-button"
                      onClick={() => model.setActiveSection(section.id)}
                    >
                      {section.label}
                    </Button>
                  ))}
                </div>
              </section>
            </nav>

            <section className="properties-panel">{activeSectionContent}</section>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

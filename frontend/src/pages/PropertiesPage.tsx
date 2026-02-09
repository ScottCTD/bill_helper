import { FormEvent, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { CreatableSingleSelect } from "../components/CreatableSingleSelect";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import {
  createEntity,
  createTag,
  createTaxonomyTerm,
  createUser,
  listCurrencies,
  listEntities,
  listTags,
  listTaxonomies,
  listTaxonomyTerms,
  listUsers,
  updateEntity,
  updateTag,
  updateTaxonomyTerm,
  updateUser
} from "../lib/api";
import {
  invalidateEntityReadModels,
  invalidateTagReadModels,
  invalidateTaxonomyReadModels,
  invalidateUserReadModels
} from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";
import type { TaxonomyTerm } from "../lib/types";

const ENTITY_CATEGORY_TAXONOMY_KEY = "entity_category";
const TAG_CATEGORY_TAXONOMY_KEY = "tag_category";

type PropertiesSectionId = "users" | "entities" | "tags" | "currencies" | "entityCategories" | "tagCategories";

const SECTION_SEARCH_DEFAULTS: Record<PropertiesSectionId, string> = {
  users: "",
  entities: "",
  tags: "",
  currencies: "",
  entityCategories: "",
  tagCategories: ""
};

const SECTION_CREATE_PANEL_DEFAULTS: Record<PropertiesSectionId, boolean> = {
  users: false,
  entities: false,
  tags: false,
  currencies: false,
  entityCategories: false,
  tagCategories: false
};

function normalizeFilterValue(value: string) {
  return value.trim().toLowerCase();
}

function includesFilter(value: string | null | undefined, query: string) {
  const normalized = normalizeFilterValue(query);
  if (!normalized) {
    return true;
  }
  return (value ?? "").toLowerCase().includes(normalized);
}

function uniqueOptionValues(values: Array<string | null | undefined>) {
  const seen = new Set<string>();
  const uniqueValues: string[] = [];
  for (const value of values) {
    const trimmed = value?.trim();
    if (!trimmed) {
      continue;
    }
    const normalized = trimmed.toLowerCase();
    if (seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    uniqueValues.push(trimmed);
  }
  return uniqueValues.sort((left, right) => left.localeCompare(right));
}

function taxonomyTermNames(terms: TaxonomyTerm[] | undefined) {
  return (terms ?? []).map((term) => term.name);
}

export function PropertiesPage() {
  const queryClient = useQueryClient();
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

  const [activeSection, setActiveSection] = useState<PropertiesSectionId>("entities");
  const [sectionSearch, setSectionSearch] = useState<Record<PropertiesSectionId, string>>({
    ...SECTION_SEARCH_DEFAULTS
  });
  const [createPanelOpen, setCreatePanelOpen] = useState<Record<PropertiesSectionId, boolean>>({
    ...SECTION_CREATE_PANEL_DEFAULTS
  });

  const [newEntityName, setNewEntityName] = useState("");
  const [newEntityCategory, setNewEntityCategory] = useState("");
  const [editingEntityId, setEditingEntityId] = useState("");
  const [editingEntityName, setEditingEntityName] = useState("");
  const [editingEntityCategory, setEditingEntityCategory] = useState("");

  const [newTagName, setNewTagName] = useState("");
  const [newTagCategory, setNewTagCategory] = useState("");
  const [newTagColor, setNewTagColor] = useState("");
  const [editingTagId, setEditingTagId] = useState<number | null>(null);
  const [editingTagName, setEditingTagName] = useState("");
  const [editingTagCategory, setEditingTagCategory] = useState("");
  const [editingTagColor, setEditingTagColor] = useState("");

  const [newUserName, setNewUserName] = useState("");
  const [editingUserId, setEditingUserId] = useState("");
  const [editingUserName, setEditingUserName] = useState("");

  const [newEntityCategoryTermName, setNewEntityCategoryTermName] = useState("");
  const [editingEntityCategoryTermId, setEditingEntityCategoryTermId] = useState("");
  const [editingEntityCategoryTermName, setEditingEntityCategoryTermName] = useState("");

  const [newTagCategoryTermName, setNewTagCategoryTermName] = useState("");
  const [editingTagCategoryTermId, setEditingTagCategoryTermId] = useState("");
  const [editingTagCategoryTermName, setEditingTagCategoryTermName] = useState("");

  const createEntityMutation = useMutation({
    mutationFn: createEntity,
    onSuccess: () => {
      setNewEntityName("");
      setNewEntityCategory("");
      setCreatePanelOpen((state) => ({ ...state, entities: false }));
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

  const createTagMutation = useMutation({
    mutationFn: createTag,
    onSuccess: () => {
      setNewTagName("");
      setNewTagCategory("");
      setNewTagColor("");
      setCreatePanelOpen((state) => ({ ...state, tags: false }));
      invalidateTagReadModels(queryClient);
    }
  });

  const updateTagMutation = useMutation({
    mutationFn: ({ tagId, name, color, category }: { tagId: number; name: string; color: string; category: string }) =>
      updateTag(tagId, { name, color: color || null, category: category || null }),
    onSuccess: () => {
      setEditingTagId(null);
      setEditingTagName("");
      setEditingTagCategory("");
      setEditingTagColor("");
      invalidateTagReadModels(queryClient);
    }
  });

  const createUserMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      setNewUserName("");
      setCreatePanelOpen((state) => ({ ...state, users: false }));
      invalidateUserReadModels(queryClient);
    }
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ userId, name }: { userId: string; name: string }) => updateUser(userId, { name }),
    onSuccess: () => {
      setEditingUserId("");
      setEditingUserName("");
      invalidateUserReadModels(queryClient);
    }
  });

  const createEntityCategoryTermMutation = useMutation({
    mutationFn: ({ name }: { name: string }) => createTaxonomyTerm(ENTITY_CATEGORY_TAXONOMY_KEY, { name }),
    onSuccess: () => {
      setNewEntityCategoryTermName("");
      setCreatePanelOpen((state) => ({ ...state, entityCategories: false }));
      invalidateTaxonomyReadModels(queryClient, ENTITY_CATEGORY_TAXONOMY_KEY);
    }
  });

  const updateEntityCategoryTermMutation = useMutation({
    mutationFn: ({ termId, name }: { termId: string; name: string }) =>
      updateTaxonomyTerm(ENTITY_CATEGORY_TAXONOMY_KEY, termId, { name }),
    onSuccess: () => {
      setEditingEntityCategoryTermId("");
      setEditingEntityCategoryTermName("");
      invalidateTaxonomyReadModels(queryClient, ENTITY_CATEGORY_TAXONOMY_KEY);
    }
  });

  const createTagCategoryTermMutation = useMutation({
    mutationFn: ({ name }: { name: string }) => createTaxonomyTerm(TAG_CATEGORY_TAXONOMY_KEY, { name }),
    onSuccess: () => {
      setNewTagCategoryTermName("");
      setCreatePanelOpen((state) => ({ ...state, tagCategories: false }));
      invalidateTaxonomyReadModels(queryClient, TAG_CATEGORY_TAXONOMY_KEY);
    }
  });

  const updateTagCategoryTermMutation = useMutation({
    mutationFn: ({ termId, name }: { termId: string; name: string }) => updateTaxonomyTerm(TAG_CATEGORY_TAXONOMY_KEY, termId, { name }),
    onSuccess: () => {
      setEditingTagCategoryTermId("");
      setEditingTagCategoryTermName("");
      invalidateTaxonomyReadModels(queryClient, TAG_CATEGORY_TAXONOMY_KEY);
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

  const filteredUsers = useMemo(() => {
    return (usersQuery.data ?? []).filter((user) => includesFilter(user.name, sectionSearch.users));
  }, [sectionSearch.users, usersQuery.data]);

  const filteredEntities = useMemo(() => {
    return (entitiesQuery.data ?? []).filter(
      (entity) =>
        includesFilter(entity.name, sectionSearch.entities) || includesFilter(entity.category, sectionSearch.entities)
    );
  }, [entitiesQuery.data, sectionSearch.entities]);

  const filteredTags = useMemo(() => {
    return (tagsQuery.data ?? []).filter(
      (tag) =>
        includesFilter(tag.name, sectionSearch.tags) ||
        includesFilter(tag.category, sectionSearch.tags) ||
        includesFilter(tag.color, sectionSearch.tags)
    );
  }, [sectionSearch.tags, tagsQuery.data]);

  const filteredCurrencies = useMemo(() => {
    return (currenciesQuery.data ?? []).filter(
      (currency) =>
        includesFilter(currency.code, sectionSearch.currencies) || includesFilter(currency.name, sectionSearch.currencies)
    );
  }, [currenciesQuery.data, sectionSearch.currencies]);

  const filteredEntityCategoryTerms = useMemo(() => {
    return (entityCategoryTermsQuery.data ?? []).filter((term) => includesFilter(term.name, sectionSearch.entityCategories));
  }, [entityCategoryTermsQuery.data, sectionSearch.entityCategories]);

  const filteredTagCategoryTerms = useMemo(() => {
    return (tagCategoryTermsQuery.data ?? []).filter((term) => includesFilter(term.name, sectionSearch.tagCategories));
  }, [sectionSearch.tagCategories, tagCategoryTermsQuery.data]);

  function setSectionSearchValue(sectionId: PropertiesSectionId, value: string) {
    setSectionSearch((state) => ({ ...state, [sectionId]: value }));
  }

  function toggleCreatePanel(sectionId: PropertiesSectionId) {
    setCreatePanelOpen((state) => ({ ...state, [sectionId]: !state[sectionId] }));
  }

  function closeCreatePanel(sectionId: PropertiesSectionId) {
    setCreatePanelOpen((state) => ({ ...state, [sectionId]: false }));
  }

  function onCreateEntity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newEntityName.trim();
    if (!name) {
      return;
    }
    createEntityMutation.mutate({ name, category: newEntityCategory.trim() || null });
  }

  function onCreateTag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newTagName.trim();
    if (!name) {
      return;
    }
    createTagMutation.mutate({
      name,
      category: newTagCategory.trim() || undefined,
      color: newTagColor.trim() || undefined
    });
  }

  function onCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newUserName.trim();
    if (!name) {
      return;
    }
    createUserMutation.mutate({ name });
  }

  function onCreateEntityCategoryTerm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newEntityCategoryTermName.trim();
    if (!name) {
      return;
    }
    createEntityCategoryTermMutation.mutate({ name });
  }

  function onCreateTagCategoryTerm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newTagCategoryTermName.trim();
    if (!name) {
      return;
    }
    createTagCategoryTermMutation.mutate({ name });
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

  let activeSectionContent: ReactNode = null;

  if (activeSection === "users") {
    activeSectionContent = (
      <div className="table-shell">
        <div className="table-shell-header">
          <div>
            <h3 className="table-shell-title">Users</h3>
            <p className="table-shell-subtitle">Manage owners available to accounts and entries.</p>
          </div>
        </div>
        <div className="table-toolbar">
          <div className="table-toolbar-filters">
            <label className="field min-w-[220px] grow">
              <span>Search</span>
              <Input
                placeholder="Filter users"
                value={sectionSearch.users}
                onChange={(event) => setSectionSearchValue("users", event.target.value)}
              />
            </label>
          </div>
          <div className="table-toolbar-action">
            <Button
              type="button"
              size="icon"
              variant="outline"
              aria-label={createPanelOpen.users ? "Cancel add user" : "Add user"}
              onClick={() => toggleCreatePanel("users")}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {createPanelOpen.users ? (
          <form className="table-inline-form" onSubmit={onCreateUser}>
            <label className="field min-w-[220px] grow">
              <span>Name</span>
              <Input placeholder="e.g. Alice" value={newUserName} onChange={(event) => setNewUserName(event.target.value)} />
            </label>
            <div className="table-inline-form-actions">
              <Button type="submit" size="sm" disabled={createUserMutation.isPending}>
                {createUserMutation.isPending ? "Creating..." : "Create"}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => closeCreatePanel("users")}>
                Cancel
              </Button>
            </div>
          </form>
        ) : null}

        {createUserMutation.error ? <p className="error">{(createUserMutation.error as Error).message}</p> : null}
        {usersQuery.isLoading ? <p>Loading users...</p> : null}
        {usersQuery.isError ? <p className="error">{(usersQuery.error as Error).message}</p> : null}

        {usersQuery.data ? (
          filteredUsers.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Current User</TableHead>
                  <TableHead>Accounts</TableHead>
                  <TableHead>Entries</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUsers.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      {editingUserId === user.id ? (
                        <Input value={editingUserName} className="h-8" onChange={(event) => setEditingUserName(event.target.value)} />
                      ) : (
                        user.name
                      )}
                    </TableCell>
                    <TableCell>{user.is_current_user ? <Badge variant="secondary">Current</Badge> : null}</TableCell>
                    <TableCell>{user.account_count ?? 0}</TableCell>
                    <TableCell>{user.entry_count ?? 0}</TableCell>
                    <TableCell>
                      {editingUserId === user.id ? (
                        <div className="table-actions">
                          <Button
                            type="button"
                            size="sm"
                            disabled={updateUserMutation.isPending}
                            onClick={() => {
                              const name = editingUserName.trim();
                              if (!name) {
                                return;
                              }
                              updateUserMutation.mutate({ userId: user.id, name });
                            }}
                          >
                            Save
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEditingUserId("");
                              setEditingUserName("");
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingUserId(user.id);
                            setEditingUserName(user.name);
                          }}
                        >
                          Edit
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="muted">{usersQuery.data.length > 0 ? "No users match the current search." : "No users yet."}</p>
          )
        ) : null}

        {updateUserMutation.error ? <p className="error">{(updateUserMutation.error as Error).message}</p> : null}
      </div>
    );
  }

  if (activeSection === "entities") {
    activeSectionContent = (
      <div className="table-shell">
        <div className="table-shell-header">
          <div>
            <h3 className="table-shell-title">Entities</h3>
            <p className="table-shell-subtitle">Manage counterparties and assign taxonomy-backed categories.</p>
          </div>
        </div>
        <div className="table-toolbar">
          <div className="table-toolbar-filters">
            <label className="field min-w-[220px] grow">
              <span>Search</span>
              <Input
                placeholder="Filter by entity or category"
                value={sectionSearch.entities}
                onChange={(event) => setSectionSearchValue("entities", event.target.value)}
              />
            </label>
          </div>
          <div className="table-toolbar-action">
            <Button
              type="button"
              size="icon"
              variant="outline"
              aria-label={createPanelOpen.entities ? "Cancel add entity" : "Add entity"}
              onClick={() => toggleCreatePanel("entities")}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {createPanelOpen.entities ? (
          <form className="table-inline-form" onSubmit={onCreateEntity}>
            <label className="field min-w-[220px] grow">
              <span>Name</span>
              <Input placeholder="e.g. Landlord" value={newEntityName} onChange={(event) => setNewEntityName(event.target.value)} />
            </label>
            <label className="field min-w-[220px] grow">
              <span>Category</span>
              <CreatableSingleSelect
                value={newEntityCategory}
                options={entityCategoryOptions}
                ariaLabel="Entity category"
                placeholder="Select or create category..."
                onChange={setNewEntityCategory}
              />
            </label>
            <div className="table-inline-form-actions">
              <Button type="submit" size="sm" disabled={createEntityMutation.isPending}>
                {createEntityMutation.isPending ? "Creating..." : "Create"}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => closeCreatePanel("entities")}>
                Cancel
              </Button>
            </div>
          </form>
        ) : null}

        {createEntityMutation.error ? <p className="error">{(createEntityMutation.error as Error).message}</p> : null}
        {entitiesQuery.isLoading ? <p>Loading entities...</p> : null}
        {entitiesQuery.isError ? <p className="error">{(entitiesQuery.error as Error).message}</p> : null}

        {entitiesQuery.data ? (
          filteredEntities.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>From</TableHead>
                  <TableHead>To</TableHead>
                  <TableHead>Accounts</TableHead>
                  <TableHead>Entries</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredEntities.map((entity) => (
                  <TableRow key={entity.id}>
                    <TableCell>
                      {editingEntityId === entity.id ? (
                        <Input value={editingEntityName} className="h-8" onChange={(event) => setEditingEntityName(event.target.value)} />
                      ) : (
                        entity.name
                      )}
                    </TableCell>
                    <TableCell>
                      {editingEntityId === entity.id ? (
                        <div className="min-w-[200px]">
                          <CreatableSingleSelect
                            value={editingEntityCategory}
                            options={entityCategoryOptions}
                            ariaLabel="Edit entity category"
                            placeholder="Select or create category..."
                            onChange={setEditingEntityCategory}
                          />
                        </div>
                      ) : (
                        entity.category || "(none)"
                      )}
                    </TableCell>
                    <TableCell>{entity.from_count ?? 0}</TableCell>
                    <TableCell>{entity.to_count ?? 0}</TableCell>
                    <TableCell>{entity.account_count ?? 0}</TableCell>
                    <TableCell>{entity.entry_count ?? 0}</TableCell>
                    <TableCell>
                      {editingEntityId === entity.id ? (
                        <div className="table-actions">
                          <Button
                            type="button"
                            size="sm"
                            disabled={updateEntityMutation.isPending}
                            onClick={() => {
                              const name = editingEntityName.trim();
                              if (!name) {
                                return;
                              }
                              updateEntityMutation.mutate({
                                entityId: entity.id,
                                name,
                                category: editingEntityCategory.trim()
                              });
                            }}
                          >
                            Save
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEditingEntityId("");
                              setEditingEntityName("");
                              setEditingEntityCategory("");
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingEntityId(entity.id);
                            setEditingEntityName(entity.name);
                            setEditingEntityCategory(entity.category ?? "");
                          }}
                        >
                          Edit
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="muted">{entitiesQuery.data.length > 0 ? "No entities match the current search." : "No entities yet."}</p>
          )
        ) : null}

        {updateEntityMutation.error ? <p className="error">{(updateEntityMutation.error as Error).message}</p> : null}
      </div>
    );
  }

  if (activeSection === "tags") {
    activeSectionContent = (
      <div className="table-shell">
        <div className="table-shell-header">
          <div>
            <h3 className="table-shell-title">Tags</h3>
            <p className="table-shell-subtitle">Manage tags, colors, and taxonomy-backed categories.</p>
          </div>
        </div>
        <div className="table-toolbar">
          <div className="table-toolbar-filters">
            <label className="field min-w-[220px] grow">
              <span>Search</span>
              <Input
                placeholder="Filter by tag, category, or color"
                value={sectionSearch.tags}
                onChange={(event) => setSectionSearchValue("tags", event.target.value)}
              />
            </label>
          </div>
          <div className="table-toolbar-action">
            <Button
              type="button"
              size="icon"
              variant="outline"
              aria-label={createPanelOpen.tags ? "Cancel add tag" : "Add tag"}
              onClick={() => toggleCreatePanel("tags")}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {createPanelOpen.tags ? (
          <form className="table-inline-form" onSubmit={onCreateTag}>
            <label className="field min-w-[200px] grow">
              <span>Name</span>
              <Input placeholder="e.g. groceries" value={newTagName} onChange={(event) => setNewTagName(event.target.value)} />
            </label>
            <label className="field min-w-[220px] grow">
              <span>Category</span>
              <CreatableSingleSelect
                value={newTagCategory}
                options={tagCategoryOptions}
                ariaLabel="Tag category"
                placeholder="Select or create category..."
                onChange={setNewTagCategory}
              />
            </label>
            <label className="field min-w-[180px]">
              <span>Color</span>
              <Input placeholder="e.g. #7fb069" value={newTagColor} onChange={(event) => setNewTagColor(event.target.value)} />
            </label>
            <div className="table-inline-form-actions">
              <Button type="submit" size="sm" disabled={createTagMutation.isPending}>
                {createTagMutation.isPending ? "Creating..." : "Create"}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => closeCreatePanel("tags")}>
                Cancel
              </Button>
            </div>
          </form>
        ) : null}

        {createTagMutation.error ? <p className="error">{(createTagMutation.error as Error).message}</p> : null}
        {tagsQuery.isLoading ? <p>Loading tags...</p> : null}
        {tagsQuery.isError ? <p className="error">{(tagsQuery.error as Error).message}</p> : null}

        {tagsQuery.data ? (
          filteredTags.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Color</TableHead>
                  <TableHead>Entries</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTags.map((tag) => (
                  <TableRow key={tag.id}>
                    <TableCell>
                      {editingTagId === tag.id ? (
                        <Input value={editingTagName} className="h-8" onChange={(event) => setEditingTagName(event.target.value)} />
                      ) : (
                        tag.name
                      )}
                    </TableCell>
                    <TableCell>
                      {editingTagId === tag.id ? (
                        <div className="min-w-[200px]">
                          <CreatableSingleSelect
                            value={editingTagCategory}
                            options={tagCategoryOptions}
                            ariaLabel="Edit tag category"
                            placeholder="Select or create category..."
                            onChange={setEditingTagCategory}
                          />
                        </div>
                      ) : (
                        tag.category || "(none)"
                      )}
                    </TableCell>
                    <TableCell>
                      {editingTagId === tag.id ? (
                        <Input value={editingTagColor} className="h-8" onChange={(event) => setEditingTagColor(event.target.value)} />
                      ) : (
                        <span className="tag-color-cell">
                          <span className="tag-color-dot" style={{ backgroundColor: tag.color || "hsl(var(--muted))" }} />
                          {tag.color || "(none)"}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>{tag.entry_count ?? 0}</TableCell>
                    <TableCell>
                      {editingTagId === tag.id ? (
                        <div className="table-actions">
                          <Button
                            type="button"
                            size="sm"
                            disabled={updateTagMutation.isPending}
                            onClick={() => {
                              const name = editingTagName.trim();
                              if (!name) {
                                return;
                              }
                              updateTagMutation.mutate({
                                tagId: tag.id,
                                name,
                                color: editingTagColor.trim(),
                                category: editingTagCategory.trim()
                              });
                            }}
                          >
                            Save
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEditingTagId(null);
                              setEditingTagName("");
                              setEditingTagCategory("");
                              setEditingTagColor("");
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingTagId(tag.id);
                            setEditingTagName(tag.name);
                            setEditingTagCategory(tag.category ?? "");
                            setEditingTagColor(tag.color ?? "");
                          }}
                        >
                          Edit
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="muted">{tagsQuery.data.length > 0 ? "No tags match the current search." : "No tags yet."}</p>
          )
        ) : null}

        {updateTagMutation.error ? <p className="error">{(updateTagMutation.error as Error).message}</p> : null}
      </div>
    );
  }

  if (activeSection === "currencies") {
    activeSectionContent = (
      <div className="table-shell">
        <div className="table-shell-header">
          <div>
            <h3 className="table-shell-title">Currencies</h3>
            <p className="table-shell-subtitle">Read-only catalog used by entries and accounts.</p>
          </div>
        </div>
        <div className="table-toolbar">
          <div className="table-toolbar-filters">
            <label className="field min-w-[220px] grow">
              <span>Search</span>
              <Input
                placeholder="Filter by code or name"
                value={sectionSearch.currencies}
                onChange={(event) => setSectionSearchValue("currencies", event.target.value)}
              />
            </label>
          </div>
        </div>

        {currenciesQuery.isLoading ? <p>Loading currencies...</p> : null}
        {currenciesQuery.isError ? <p className="error">{(currenciesQuery.error as Error).message}</p> : null}

        {currenciesQuery.data ? (
          filteredCurrencies.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Entries</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCurrencies.map((currency) => (
                  <TableRow key={currency.code}>
                    <TableCell>{currency.code}</TableCell>
                    <TableCell>{currency.name}</TableCell>
                    <TableCell>{currency.entry_count}</TableCell>
                    <TableCell>{currency.is_placeholder ? "Placeholder" : "Built-in"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="muted">
              {currenciesQuery.data.length > 0 ? "No currencies match the current search." : "No currencies yet."}
            </p>
          )
        ) : null}
      </div>
    );
  }

  if (activeSection === "entityCategories") {
    activeSectionContent = (
      <div className="table-shell">
        <div className="table-shell-header">
          <div>
            <h3 className="table-shell-title">{entityCategoriesLabel}</h3>
            <p className="table-shell-subtitle">Flat taxonomy terms used by entities. Usage equals assigned entities.</p>
          </div>
        </div>
        <div className="table-toolbar">
          <div className="table-toolbar-filters">
            <label className="field min-w-[220px] grow">
              <span>Search</span>
              <Input
                placeholder="Filter categories"
                value={sectionSearch.entityCategories}
                onChange={(event) => setSectionSearchValue("entityCategories", event.target.value)}
              />
            </label>
          </div>
          <div className="table-toolbar-action">
            <Button
              type="button"
              size="icon"
              variant="outline"
              aria-label={createPanelOpen.entityCategories ? "Cancel add category" : "Add category"}
              onClick={() => toggleCreatePanel("entityCategories")}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {createPanelOpen.entityCategories ? (
          <form className="table-inline-form" onSubmit={onCreateEntityCategoryTerm}>
            <label className="field min-w-[220px] grow">
              <span>Name</span>
              <Input
                placeholder="e.g. merchant"
                value={newEntityCategoryTermName}
                onChange={(event) => setNewEntityCategoryTermName(event.target.value)}
              />
            </label>
            <div className="table-inline-form-actions">
              <Button type="submit" size="sm" disabled={createEntityCategoryTermMutation.isPending}>
                {createEntityCategoryTermMutation.isPending ? "Creating..." : "Create"}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => closeCreatePanel("entityCategories")}>
                Cancel
              </Button>
            </div>
          </form>
        ) : null}

        {createEntityCategoryTermMutation.error ? (
          <p className="error">{(createEntityCategoryTermMutation.error as Error).message}</p>
        ) : null}
        {entityCategoryTermsQuery.isLoading ? <p>Loading categories...</p> : null}
        {entityCategoryTermsQuery.isError ? <p className="error">{(entityCategoryTermsQuery.error as Error).message}</p> : null}

        {entityCategoryTermsQuery.data ? (
          filteredEntityCategoryTerms.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Usage</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredEntityCategoryTerms.map((term) => (
                  <TableRow key={term.id}>
                    <TableCell>
                      {editingEntityCategoryTermId === term.id ? (
                        <Input
                          value={editingEntityCategoryTermName}
                          className="h-8"
                          onChange={(event) => setEditingEntityCategoryTermName(event.target.value)}
                        />
                      ) : (
                        term.name
                      )}
                    </TableCell>
                    <TableCell>{term.usage_count}</TableCell>
                    <TableCell>
                      {editingEntityCategoryTermId === term.id ? (
                        <div className="table-actions">
                          <Button
                            type="button"
                            size="sm"
                            disabled={updateEntityCategoryTermMutation.isPending}
                            onClick={() => {
                              const name = editingEntityCategoryTermName.trim();
                              if (!name) {
                                return;
                              }
                              updateEntityCategoryTermMutation.mutate({ termId: term.id, name });
                            }}
                          >
                            Save
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEditingEntityCategoryTermId("");
                              setEditingEntityCategoryTermName("");
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingEntityCategoryTermId(term.id);
                            setEditingEntityCategoryTermName(term.name);
                          }}
                        >
                          Rename
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="muted">
              {entityCategoryTermsQuery.data.length > 0 ? "No categories match the current search." : "No categories yet."}
            </p>
          )
        ) : null}

        {updateEntityCategoryTermMutation.error ? (
          <p className="error">{(updateEntityCategoryTermMutation.error as Error).message}</p>
        ) : null}
      </div>
    );
  }

  if (activeSection === "tagCategories") {
    activeSectionContent = (
      <div className="table-shell">
        <div className="table-shell-header">
          <div>
            <h3 className="table-shell-title">{tagCategoriesLabel}</h3>
            <p className="table-shell-subtitle">Flat taxonomy terms used by tags. Usage equals assigned tags.</p>
          </div>
        </div>
        <div className="table-toolbar">
          <div className="table-toolbar-filters">
            <label className="field min-w-[220px] grow">
              <span>Search</span>
              <Input
                placeholder="Filter categories"
                value={sectionSearch.tagCategories}
                onChange={(event) => setSectionSearchValue("tagCategories", event.target.value)}
              />
            </label>
          </div>
          <div className="table-toolbar-action">
            <Button
              type="button"
              size="icon"
              variant="outline"
              aria-label={createPanelOpen.tagCategories ? "Cancel add category" : "Add category"}
              onClick={() => toggleCreatePanel("tagCategories")}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {createPanelOpen.tagCategories ? (
          <form className="table-inline-form" onSubmit={onCreateTagCategoryTerm}>
            <label className="field min-w-[220px] grow">
              <span>Name</span>
              <Input
                placeholder="e.g. food"
                value={newTagCategoryTermName}
                onChange={(event) => setNewTagCategoryTermName(event.target.value)}
              />
            </label>
            <div className="table-inline-form-actions">
              <Button type="submit" size="sm" disabled={createTagCategoryTermMutation.isPending}>
                {createTagCategoryTermMutation.isPending ? "Creating..." : "Create"}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => closeCreatePanel("tagCategories")}>
                Cancel
              </Button>
            </div>
          </form>
        ) : null}

        {createTagCategoryTermMutation.error ? <p className="error">{(createTagCategoryTermMutation.error as Error).message}</p> : null}
        {tagCategoryTermsQuery.isLoading ? <p>Loading categories...</p> : null}
        {tagCategoryTermsQuery.isError ? <p className="error">{(tagCategoryTermsQuery.error as Error).message}</p> : null}

        {tagCategoryTermsQuery.data ? (
          filteredTagCategoryTerms.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Usage</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTagCategoryTerms.map((term) => (
                  <TableRow key={term.id}>
                    <TableCell>
                      {editingTagCategoryTermId === term.id ? (
                        <Input
                          value={editingTagCategoryTermName}
                          className="h-8"
                          onChange={(event) => setEditingTagCategoryTermName(event.target.value)}
                        />
                      ) : (
                        term.name
                      )}
                    </TableCell>
                    <TableCell>{term.usage_count}</TableCell>
                    <TableCell>
                      {editingTagCategoryTermId === term.id ? (
                        <div className="table-actions">
                          <Button
                            type="button"
                            size="sm"
                            disabled={updateTagCategoryTermMutation.isPending}
                            onClick={() => {
                              const name = editingTagCategoryTermName.trim();
                              if (!name) {
                                return;
                              }
                              updateTagCategoryTermMutation.mutate({ termId: term.id, name });
                            }}
                          >
                            Save
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEditingTagCategoryTermId("");
                              setEditingTagCategoryTermName("");
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingTagCategoryTermId(term.id);
                            setEditingTagCategoryTermName(term.name);
                          }}
                        >
                          Rename
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="muted">{tagCategoryTermsQuery.data.length > 0 ? "No categories match the current search." : "No categories yet."}</p>
          )
        ) : null}

        {updateTagCategoryTermMutation.error ? <p className="error">{(updateTagCategoryTermMutation.error as Error).message}</p> : null}
      </div>
    );
  }

  return (
    <div className="stack-lg">
      <Card>
        <CardContent className="space-y-5 pt-6">
          <div className="space-y-1.5">
            <h2 className="text-xl font-semibold">Property Databases</h2>
            <p className="muted">
              Manage core catalogs and taxonomy terms from one workspace. Category pickers for entities and tags are driven by
              taxonomy terms.
            </p>
            {taxonomiesQuery.isError ? <p className="error">{(taxonomiesQuery.error as Error).message}</p> : null}
          </div>

          <div className="properties-layout">
            <nav className="properties-nav" aria-label="Property sections">
              <section className="properties-nav-group">
                <p className="properties-nav-label">Core</p>
                <div className="properties-nav-list">
                  {coreSections.map((section) => (
                    <Button
                      key={section.id}
                      type="button"
                      size="sm"
                      variant={activeSection === section.id ? "secondary" : "ghost"}
                      className="properties-nav-button"
                      onClick={() => setActiveSection(section.id)}
                    >
                      {section.label}
                    </Button>
                  ))}
                </div>
              </section>

              <section className="properties-nav-group">
                <p className="properties-nav-label">Taxonomies</p>
                <div className="properties-nav-list">
                  {taxonomySections.map((section) => (
                    <Button
                      key={section.id}
                      type="button"
                      size="sm"
                      variant={activeSection === section.id ? "secondary" : "ghost"}
                      className="properties-nav-button"
                      onClick={() => setActiveSection(section.id)}
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

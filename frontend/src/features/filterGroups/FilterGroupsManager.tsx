import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { createFilterGroup, deleteFilterGroup, listFilterGroups, updateFilterGroup } from "../../lib/api";
import { invalidateFilterGroupReadModels } from "../../lib/queryInvalidation";
import { queryKeys } from "../../lib/queryKeys";
import type { FilterGroup } from "../../lib/types";
import { FilterGroupEditorCard } from "./FilterGroupEditorCard";

export function FilterGroupsManager() {
  const queryClient = useQueryClient();
  const filterGroupsQuery = useQuery({
    queryKey: queryKeys.filterGroups.list,
    queryFn: listFilterGroups
  });
  const createMutation = useMutation({
    mutationFn: createFilterGroup,
    onSuccess: () => {
      setIsCreateOpen(false);
      invalidateFilterGroupReadModels(queryClient);
    }
  });
  const updateMutation = useMutation({
    mutationFn: ({ filterGroupId, payload }: { filterGroupId: string; payload: Parameters<typeof updateFilterGroup>[1] }) =>
      updateFilterGroup(filterGroupId, payload),
    onSuccess: () => {
      setActiveUpdateId(null);
      invalidateFilterGroupReadModels(queryClient);
    },
    onError: () => {
      setActiveUpdateId(null);
    }
  });
  const deleteMutation = useMutation({
    mutationFn: deleteFilterGroup,
    onSuccess: () => {
      setActiveDeleteId(null);
      invalidateFilterGroupReadModels(queryClient);
    },
    onError: () => {
      setActiveDeleteId(null);
    }
  });
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [activeUpdateId, setActiveUpdateId] = useState<string | null>(null);
  const [activeDeleteId, setActiveDeleteId] = useState<string | null>(null);

  const filterGroups = filterGroupsQuery.data ?? [];
  const mutationError =
    (createMutation.error as Error | null)?.message ??
    (updateMutation.error as Error | null)?.message ??
    (deleteMutation.error as Error | null)?.message ??
    null;

  function saveFilterGroup(filterGroup: FilterGroup, payload: { name: string; description: string | null; color: string | null; rule: FilterGroup["rule"] }) {
    setActiveUpdateId(filterGroup.id);
    updateMutation.mutate({
      filterGroupId: filterGroup.id,
      payload: {
        name: payload.name,
        description: payload.description,
        color: payload.color,
        rule: payload.rule
      }
    });
  }

  function removeFilterGroup(filterGroupId: string) {
    setActiveDeleteId(filterGroupId);
    deleteMutation.mutate(filterGroupId);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Saved Filter Groups</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="muted text-sm">
            These rules drive dashboard classification and entry filtering. Default groups can have their logic edited, but their names stay fixed.
          </p>
          <Button type="button" variant="outline" onClick={() => setIsCreateOpen((current) => !current)}>
            {isCreateOpen ? "Hide new group" : "New custom group"}
          </Button>
        </div>

        {mutationError ? <p className="error">{mutationError}</p> : null}
        {filterGroupsQuery.isError ? <p className="error">Failed to load filter groups: {(filterGroupsQuery.error as Error).message}</p> : null}

        {isCreateOpen ? (
          <FilterGroupEditorCard
            submitLabel="Create group"
            isPending={createMutation.isPending}
            onCancel={() => setIsCreateOpen(false)}
            onSubmit={(payload) => createMutation.mutate(payload)}
          />
        ) : null}

        {filterGroups.map((filterGroup) => (
          <div key={filterGroup.id} className="space-y-3">
            <div className="flex justify-end">
              <Button asChild type="button" variant="ghost" size="sm">
                <Link to={`/entries?filter_group_id=${filterGroup.id}`}>View matching entries</Link>
              </Button>
            </div>
            <FilterGroupEditorCard
              filterGroup={filterGroup}
              submitLabel="Save changes"
              isPending={activeUpdateId === filterGroup.id || activeDeleteId === filterGroup.id}
              onSubmit={(payload) => saveFilterGroup(filterGroup, payload)}
              onDelete={filterGroup.is_default ? undefined : () => removeFilterGroup(filterGroup.id)}
            />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

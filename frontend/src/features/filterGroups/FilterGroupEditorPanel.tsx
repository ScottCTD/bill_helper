/**
 * CALLING SPEC:
 * - Purpose: render the focused detail editor for one selected filter group.
 * - Inputs: callers that provide editor session state, tag catalog data, and CRUD handlers.
 * - Outputs: React UI for editing one filter group.
 * - Side effects: React rendering and user event wiring.
 */
import { Link } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Textarea } from "../../components/ui/textarea";
import type { Tag } from "../../lib/types";
import type { FilterGroupEditorFormState, FilterGroupEditorSession } from "./filterGroupEditorState";
import { FilterRuleSectionEditor } from "./FilterRuleSectionEditor";
import { createEmptyGroup } from "./filterGroupRuleUtils";

interface FilterGroupEditorPanelProps {
  session: FilterGroupEditorSession;
  tags: Tag[];
  preferredTagName?: string;
  isDirty: boolean;
  isPending: boolean;
  mutationError?: string | null;
  tagLoadError?: string | null;
  onChange: (nextFormState: FilterGroupEditorFormState) => void;
  onSubmit: () => void;
  onDelete?: () => void;
}

export function FilterGroupEditorPanel({
  session,
  tags,
  preferredTagName,
  isDirty,
  isPending,
  mutationError,
  tagLoadError,
  onChange,
  onSubmit,
  onDelete
}: FilterGroupEditorPanelProps) {
  const saveLabel = session.kind === "new" ? "Create group" : "Save changes";
  const title = session.formState.name.trim() || (session.kind === "new" ? "New custom group" : "Unnamed filter group");

  function updateFormState(patch: Partial<FilterGroupEditorFormState>) {
    onChange({
      ...session.formState,
      ...patch
    });
  }

  return (
    <Card className="min-w-0 border-border/90">
      <CardHeader className="grid gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="grid gap-2">
            <CardTitle>{title}</CardTitle>
            <div className="flex flex-wrap gap-2">
              <Badge variant={session.isDefault ? "secondary" : "outline"}>{session.isDefault ? "Default" : session.kind === "new" ? "Draft" : "Custom"}</Badge>
              {isDirty ? <Badge variant="outline">Unsaved changes</Badge> : null}
            </div>
          </div>
          {session.kind === "existing" ? (
            <Button asChild type="button" variant="outline" size="sm">
              <Link to={`/entries?filter_group_id=${session.filterGroupId}`}>View matching entries</Link>
            </Button>
          ) : null}
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr),180px]">
          <label className="field min-w-0">
            <span>Name</span>
            <Input
              value={session.formState.name}
              onChange={(event) => updateFormState({ name: event.target.value })}
              disabled={session.kind === "existing" && session.isDefault}
              placeholder="e.g. Routine spending"
            />
          </label>
          <label className="field min-w-0">
            <span>Chart color</span>
            <Input type="color" value={session.formState.color} onChange={(event) => updateFormState({ color: event.target.value })} />
          </label>
        </div>

        <label className="field min-w-0">
          <span>Description</span>
          <Textarea
            rows={3}
            value={session.formState.description}
            onChange={(event) => updateFormState({ description: event.target.value })}
            placeholder="Explain what this filter group is for."
          />
        </label>
      </CardHeader>

      <CardContent className="grid gap-4">
        <FilterRuleSectionEditor
          title="Include when"
          description="Choose the rules an entry must match to land in this group."
          group={session.formState.rule.include}
          tags={tags}
          preferredTagName={preferredTagName}
          onChange={(nextIncludeGroup) =>
            updateFormState({
              rule: {
                ...session.formState.rule,
                include: nextIncludeGroup
              }
            })
          }
        />

        {session.formState.rule.exclude ? (
          <FilterRuleSectionEditor
            title="Exclude when"
            description="Remove entries from this group when any exclusion rule matches."
            group={session.formState.rule.exclude}
            tags={tags}
            preferredTagName={preferredTagName}
            removeSectionLabel="Remove exclusion"
            onChange={(nextExcludeGroup) =>
              updateFormState({
                rule: {
                  ...session.formState.rule,
                  exclude: nextExcludeGroup
                }
              })
            }
            onRemoveSection={() =>
              updateFormState({
                rule: {
                  ...session.formState.rule,
                  exclude: null
                }
              })
            }
          />
        ) : (
          <div className="rounded-2xl border border-dashed border-border bg-secondary/25 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="grid gap-1">
                <h3 className="text-sm font-semibold">Exclude when</h3>
                <p className="text-sm text-muted-foreground">Optional rules that explicitly keep matching entries out of this group.</p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  updateFormState({
                    rule: {
                      ...session.formState.rule,
                      exclude: createEmptyGroup("is_internal_transfer", preferredTagName)
                    }
                  })
                }
              >
                Add exclusion
              </Button>
            </div>
          </div>
        )}

        {tagLoadError ? <p className="error">Failed to load tags for the editor: {tagLoadError}</p> : null}
        {mutationError ? <p className="error">{mutationError}</p> : null}

        <div className="flex flex-wrap justify-end gap-2">
          {onDelete ? (
            <Button type="button" variant="outline" disabled={isPending} onClick={onDelete}>
              Delete
            </Button>
          ) : null}
          <Button type="button" disabled={isPending || !session.formState.name.trim() || !isDirty} onClick={onSubmit}>
            {isPending ? "Saving..." : saveLabel}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

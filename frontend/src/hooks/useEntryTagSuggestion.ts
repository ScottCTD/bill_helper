/**
 * CALLING SPEC:
 * - Purpose: provide the `useEntryTagSuggestion` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/hooks/useEntryTagSuggestion.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `useEntryTagSuggestion`.
 * - Side effects: client-side state coordination and query wiring.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { useNotifications } from "../components/ui/notification-center";
import { suggestEntryTags } from "../lib/api";
import type { EntryTagSuggestionRequest } from "../lib/types";

interface UseEntryTagSuggestionArgs {
  entryTaggingModel: string | null | undefined;
  buildDraft: () => EntryTagSuggestionRequest;
  onApplySuggestion: (suggestedTags: string[]) => void;
}

function hasMeaningfulTaggingContext(draft: EntryTagSuggestionRequest): boolean {
  return Boolean(
    draft.name?.trim() ||
      draft.amount_minor ||
      draft.from_entity_id ||
      draft.from_entity?.trim() ||
      draft.to_entity_id ||
      draft.to_entity?.trim() ||
      draft.markdown_body?.trim() ||
      draft.current_tags.some((tag) => tag.trim())
  );
}

export function useEntryTagSuggestion({
  entryTaggingModel,
  buildDraft,
  onApplySuggestion,
}: UseEntryTagSuggestionArgs) {
  const { notify } = useNotifications();
  const [isRunning, setIsRunning] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const requestVersionRef = useRef(0);

  const cancelSuggestion = useCallback(() => {
    requestVersionRef.current += 1;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsRunning(false);
  }, []);

  useEffect(() => cancelSuggestion, [cancelSuggestion]);

  const requestSuggestion = useCallback(async () => {
    if (isRunning) {
      cancelSuggestion();
      return;
    }

    if (!entryTaggingModel?.trim()) {
      notify({
        title: "AI tag suggestion is disabled until you set Default tagging model in Settings.",
        tone: "info",
      });
      return;
    }

    const draft = buildDraft();
    if (!hasMeaningfulTaggingContext(draft)) {
      notify({
        title: "Add a name, amount, entity, notes, or tags before asking AI for tag suggestions.",
        tone: "info",
      });
      return;
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;
    const requestVersion = requestVersionRef.current + 1;
    requestVersionRef.current = requestVersion;
    setIsRunning(true);

    try {
      const response = await suggestEntryTags({
        ...draft,
        signal: controller.signal,
      });
      if (abortControllerRef.current !== controller || requestVersionRef.current !== requestVersion) {
        return;
      }
      onApplySuggestion(response.suggested_tags);
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        return;
      }
      notify({
        title: "AI tag suggestion failed.",
        description: (error as Error).message,
        tone: "error",
        durationMs: 5600,
      });
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
      if (requestVersionRef.current === requestVersion) {
        setIsRunning(false);
      }
    }
  }, [buildDraft, cancelSuggestion, entryTaggingModel, isRunning, notify, onApplySuggestion]);

  return {
    cancelSuggestion,
    isRunning,
    requestSuggestion,
  };
}

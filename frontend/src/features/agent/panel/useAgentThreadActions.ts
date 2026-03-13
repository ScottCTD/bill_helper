/**
 * CALLING SPEC:
 * - Purpose: provide the `useAgentThreadActions` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/features/agent/panel/useAgentThreadActions.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `useAgentThreadActions`.
 * - Side effects: client-side state coordination and query wiring.
 */
import { useCallback, useState, type Dispatch, type SetStateAction } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  approveAgentChangeItem,
  createAgentThread,
  deleteAgentThread,
  interruptAgentRun,
  reopenAgentChangeItem,
  renameAgentThread,
  rejectAgentChangeItem
} from "../../../lib/api";
import { invalidateAgentThreadData, invalidateEntryReadModels } from "../../../lib/queryInvalidation";
import { queryKeys } from "../../../lib/queryKeys";
import type { AgentChangeItem, AgentThreadDetail, AgentThreadSummary } from "../../../lib/types";

interface UseAgentThreadActionsArgs {
  selectedThreadId: string;
  setSelectedThreadId: Dispatch<SetStateAction<string>>;
}

export function useAgentThreadActions({
  selectedThreadId,
  setSelectedThreadId
}: UseAgentThreadActionsArgs) {
  const queryClient = useQueryClient();
  const [optimisticThreadTitlesById, setOptimisticThreadTitlesById] = useState<Record<string, string>>({});
  const [optimisticRunningThreadIds, setOptimisticRunningThreadIds] = useState<string[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);

  const addOptimisticRunningThreadId = useCallback((threadId: string) => {
    setOptimisticRunningThreadIds((current) => (current.includes(threadId) ? current : [...current, threadId]));
  }, []);

  const removeOptimisticRunningThreadId = useCallback((threadId: string) => {
    setOptimisticRunningThreadIds((current) => current.filter((item) => item !== threadId));
  }, []);

  const pruneOptimisticRunningThreadIds = useCallback((threads: AgentThreadSummary[]) => {
    setOptimisticRunningThreadIds((current) =>
      current.filter((threadId) => {
        const matchingThread = threads.find((thread) => thread.id === threadId);
        return !matchingThread || matchingThread.has_running_run;
      })
    );
  }, []);

  const createThreadMutation = useMutation({
    mutationFn: createAgentThread,
    onSuccess: (thread) => {
      invalidateAgentThreadData(queryClient);
      setSelectedThreadId(thread.id);
    }
  });

  const deleteThreadMutation = useMutation({
    mutationFn: deleteAgentThread,
    onSuccess: (_, deletedThreadId) => {
      const currentThreads = (queryClient.getQueryData(queryKeys.agent.threads) as AgentThreadSummary[] | undefined) ?? [];
      const remainingThreads = currentThreads.filter((thread) => thread.id !== deletedThreadId);
      queryClient.setQueryData(queryKeys.agent.threads, remainingThreads);
      queryClient.removeQueries({ queryKey: queryKeys.agent.thread(deletedThreadId), exact: true });
      setSelectedThreadId((currentSelectedThreadId) =>
        currentSelectedThreadId === deletedThreadId ? (remainingThreads[0]?.id ?? "") : currentSelectedThreadId
      );
      removeOptimisticRunningThreadId(deletedThreadId);
      setActionError(null);
      invalidateAgentThreadData(queryClient);
    }
  });

  const applyThreadTitleToCaches = useCallback(
    (threadId: string, title: string | null, updatedAt: string = new Date().toISOString()) => {
      setOptimisticThreadTitlesById((current) => {
        if (!title) {
          return current;
        }
        return { ...current, [threadId]: title };
      });
      queryClient.setQueryData(queryKeys.agent.threads, (current: AgentThreadSummary[] | undefined) => {
        if (!current) {
          return current;
        }
        return [...current]
          .map((thread) => (thread.id === threadId ? { ...thread, title, updated_at: updatedAt } : thread))
          .sort((left, right) => right.updated_at.localeCompare(left.updated_at));
      });
      queryClient.setQueryData(queryKeys.agent.thread(threadId), (current: AgentThreadDetail | undefined) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          thread: {
            ...current.thread,
            title,
            updated_at: updatedAt
          }
        };
      });
    },
    [queryClient]
  );

  const clearOptimisticThreadTitle = useCallback((threadId: string) => {
    setOptimisticThreadTitlesById((current) => {
      if (!(threadId in current)) {
        return current;
      }
      const next = { ...current };
      delete next[threadId];
      return next;
    });
  }, []);

  const upsertThreadSummary = useCallback(
    (thread: AgentThreadSummary) => {
      queryClient.setQueryData(queryKeys.agent.threads, (current: AgentThreadSummary[] | undefined) => {
        const nextThreads = [thread, ...(current ?? []).filter((item) => item.id !== thread.id)];
        return nextThreads.sort((left, right) => right.updated_at.localeCompare(left.updated_at));
      });
    },
    [queryClient]
  );

  const renameThreadMutation = useMutation({
    mutationFn: renameAgentThread,
    onSuccess: (thread) => {
      applyThreadTitleToCaches(thread.id, thread.title, thread.updated_at);
      clearOptimisticThreadTitle(thread.id);
      setActionError(null);
    }
  });

  const interruptRunMutation = useMutation({
    mutationFn: (payload: { runId: string; threadId: string }) => interruptAgentRun(payload.runId),
    onSuccess: (_, payload) => {
      invalidateAgentThreadData(queryClient, payload.threadId || undefined);
      setActionError(null);
    }
  });

  const approveMutation = useMutation({
    mutationFn: approveAgentChangeItem,
    onSuccess: () => {
      invalidateAgentThreadData(queryClient, selectedThreadId || undefined);
      invalidateEntryReadModels(queryClient);
      setActionError(null);
    }
  });

  const rejectMutation = useMutation({
    mutationFn: rejectAgentChangeItem,
    onSuccess: () => {
      invalidateAgentThreadData(queryClient, selectedThreadId || undefined);
      setActionError(null);
    }
  });

  const reopenMutation = useMutation({
    mutationFn: reopenAgentChangeItem,
    onSuccess: () => {
      invalidateAgentThreadData(queryClient, selectedThreadId || undefined);
      setActionError(null);
    }
  });

  const isMutating =
    createThreadMutation.isPending ||
    deleteThreadMutation.isPending ||
    renameThreadMutation.isPending ||
    approveMutation.isPending ||
    rejectMutation.isPending ||
    reopenMutation.isPending;

  async function ensureThreadId(): Promise<string> {
    if (selectedThreadId) {
      return selectedThreadId;
    }
    const created = await createThreadMutation.mutateAsync({});
    setSelectedThreadId(created.id);
    return created.id;
  }

  async function createThread() {
    setActionError(null);
    return createThreadMutation.mutateAsync({});
  }

  async function deleteThread(threadId: string): Promise<void> {
    await deleteThreadMutation.mutateAsync(threadId);
  }

  async function renameThread(threadId: string, title: string) {
    setActionError(null);
    try {
      await renameThreadMutation.mutateAsync({ threadId, title });
    } catch (error) {
      setActionError((error as Error).message);
      throw error;
    }
  }

  async function approveItem(payload: {
    itemId: string;
    payloadOverride?: Record<string, unknown>;
  }): Promise<AgentChangeItem> {
    setActionError(null);
    try {
      return await approveMutation.mutateAsync({
        itemId: payload.itemId,
        payload_override: payload.payloadOverride
      });
    } catch (error) {
      invalidateAgentThreadData(queryClient, selectedThreadId || undefined);
      setActionError((error as Error).message);
      throw error;
    }
  }

  async function rejectItem(payload: {
    itemId: string;
    payloadOverride?: Record<string, unknown>;
  }): Promise<AgentChangeItem> {
    setActionError(null);
    try {
      return await rejectMutation.mutateAsync({
        itemId: payload.itemId,
        payload_override: payload.payloadOverride
      });
    } catch (error) {
      setActionError((error as Error).message);
      throw error;
    }
  }

  async function reopenItem(payload: {
    itemId: string;
    payloadOverride?: Record<string, unknown>;
  }): Promise<AgentChangeItem> {
    setActionError(null);
    try {
      return await reopenMutation.mutateAsync({
        itemId: payload.itemId,
        payload_override: payload.payloadOverride
      });
    } catch (error) {
      setActionError((error as Error).message);
      throw error;
    }
  }

  return {
    actionError,
    addOptimisticRunningThreadId,
    applyThreadTitleToCaches,
    approveItem,
    clearOptimisticThreadTitle,
    createThread,
    createThreadMutation,
    deleteThread,
    deleteThreadMutation,
    ensureThreadId,
    interruptRunMutation,
    isMutating,
    optimisticRunningThreadIds,
    optimisticThreadTitlesById,
    pruneOptimisticRunningThreadIds,
    removeOptimisticRunningThreadId,
    renameThread,
    renameThreadMutation,
    rejectItem,
    reopenItem,
    setActionError,
    upsertThreadSummary
  };
}

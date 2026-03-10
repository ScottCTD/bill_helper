import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  approveAgentChangeItem,
  createAgentThread,
  deleteAgentThread,
  getAgentThread,
  getRuntimeSettings,
  interruptAgentRun,
  listAgentThreads,
  reopenAgentChangeItem,
  renameAgentThread,
  rejectAgentChangeItem
} from "../../../lib/api";
import { invalidateAgentThreadData, invalidateEntryReadModels } from "../../../lib/queryInvalidation";
import { queryKeys } from "../../../lib/queryKeys";
import type { AgentChangeItem, AgentThreadDetail, AgentThreadSummary } from "../../../lib/types";
import { useResizablePanel } from "../../../hooks/useResizablePanel";
import { buildThreadUsageTotals, runsByAssistantMessage, runsWithoutAssistantMessage, runsWithoutAssistantMessageByUserMessage } from "../activity";
import { useAgentComposerRuntime } from "./useAgentComposerRuntime";

interface UseAgentPanelControllerArgs {
  isOpen: boolean;
}

export function useAgentPanelController({ isOpen }: UseAgentPanelControllerArgs) {
  const queryClient = useQueryClient();
  const [selectedThreadId, setSelectedThreadId] = useState<string>("");
  const [optimisticThreadTitlesById, setOptimisticThreadTitlesById] = useState<Record<string, string>>({});
  const [optimisticRunningThreadIds, setOptimisticRunningThreadIds] = useState<string[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isThreadReviewOpen, setIsThreadReviewOpen] = useState(false);
  const [isThreadPanelOpen, setIsThreadPanelOpen] = useState(true);
  const [isBulkLaunching, setIsBulkLaunching] = useState(false);
  const [isStreamHealthy, setIsStreamHealthy] = useState(false);
  const { panelWidth, handleMouseDown: handleResizeMouseDown } = useResizablePanel({
    storageKey: "agent-thread-panel-width",
    defaultWidth: 300,
    minWidth: 200,
    maxWidth: 600,
    edge: "right"
  });
  const toggleThreadPanel = useCallback(() => setIsThreadPanelOpen((value) => !value), []);

  const threadsQuery = useQuery({
    queryKey: queryKeys.agent.threads,
    queryFn: listAgentThreads,
    enabled: isOpen,
    refetchInterval: (query) => {
      const threads = query.state.data as AgentThreadSummary[] | undefined;
      const hasRunningThread = (threads ?? []).some((thread) => thread.has_running_run);
      return hasRunningThread || optimisticRunningThreadIds.length > 0 || isBulkLaunching ? 5000 : false;
    },
    refetchIntervalInBackground: true
  });
  const runtimeSettingsQuery = useQuery({
    queryKey: queryKeys.settings.runtime,
    queryFn: getRuntimeSettings,
    enabled: isOpen
  });
  const threadQuery = useQuery({
    queryKey: queryKeys.agent.thread(selectedThreadId),
    queryFn: () => getAgentThread(selectedThreadId),
    enabled: isOpen && Boolean(selectedThreadId),
    refetchInterval: (query) => {
      const detail = query.state.data as AgentThreadDetail | undefined;
      const hasRunningRun = (detail?.runs ?? []).some((run) => run.status === "running");
      return hasRunningRun && !isStreamHealthy ? 5000 : false;
    },
    refetchIntervalInBackground: true
  });

  const displayedThreads = useMemo(() => {
    if (!threadsQuery.data) {
      return threadsQuery.data;
    }
    return threadsQuery.data.map((thread) => {
      const optimisticTitle = optimisticThreadTitlesById[thread.id];
      return optimisticTitle ? { ...thread, title: optimisticTitle } : thread;
    });
  }, [optimisticThreadTitlesById, threadsQuery.data]);

  useEffect(() => {
    if (!isOpen || selectedThreadId) {
      return;
    }
    const firstId = threadsQuery.data?.[0]?.id;
    if (firstId) {
      setSelectedThreadId(firstId);
    }
  }, [isOpen, selectedThreadId, threadsQuery.data]);

  useEffect(() => {
    if (!threadsQuery.data) {
      return;
    }
    setOptimisticRunningThreadIds((current) =>
      current.filter((threadId) => {
        const matchingThread = threadsQuery.data?.find((thread) => thread.id === threadId);
        return !matchingThread || matchingThread.has_running_run;
      })
    );
  }, [threadsQuery.data]);

  const addOptimisticRunningThreadId = useCallback((threadId: string) => {
    setOptimisticRunningThreadIds((current) => (current.includes(threadId) ? current : [...current, threadId]));
  }, []);

  const removeOptimisticRunningThreadId = useCallback((threadId: string) => {
    setOptimisticRunningThreadIds((current) => current.filter((item) => item !== threadId));
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
      setIsThreadReviewOpen(false);
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
    mutationFn: interruptAgentRun,
    onSuccess: () => {
      invalidateAgentThreadData(queryClient, selectedThreadId || undefined);
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
    interruptRunMutation.isPending ||
    approveMutation.isPending ||
    rejectMutation.isPending ||
    reopenMutation.isPending;

  const runsByAssistantMessageId = useMemo(() => runsByAssistantMessage(threadQuery.data), [threadQuery.data]);
  const pendingAssistantRuns = useMemo(() => runsWithoutAssistantMessage(threadQuery.data), [threadQuery.data]);
  const pendingAssistantRunsByUserMessageId = useMemo(
    () => runsWithoutAssistantMessageByUserMessage(threadQuery.data),
    [threadQuery.data]
  );
  const reviewProposalCount = useMemo(
    () => (threadQuery.data?.runs ?? []).reduce((total, run) => total + run.change_items.length, 0),
    [threadQuery.data?.runs]
  );
  const pendingReviewCount = useMemo(
    () =>
      (threadQuery.data?.runs ?? []).reduce(
        (total, run) => total + run.change_items.filter((item) => item.status === "PENDING_REVIEW").length,
        0
      ),
    [threadQuery.data?.runs]
  );
  const threadUsageTotals = useMemo(() => buildThreadUsageTotals(threadQuery.data), [threadQuery.data]);

  async function ensureThreadId(): Promise<string> {
    if (selectedThreadId) {
      return selectedThreadId;
    }
    const created = await createThreadMutation.mutateAsync({});
    setSelectedThreadId(created.id);
    return created.id;
  }

  const runtime = useAgentComposerRuntime({
    actionError,
    addOptimisticRunningThreadId,
    applyThreadTitleToCaches,
    availableComposerModels: runtimeSettingsQuery.data?.available_agent_models ?? [],
    clearOptimisticThreadTitle,
    ensureThreadId,
    async interruptRun(runId: string) {
      await interruptRunMutation.mutateAsync(runId);
    },
    isBulkLaunching,
    isInterruptPending: interruptRunMutation.isPending,
    isMutating,
    removeOptimisticRunningThreadId,
    runtimeSettings: runtimeSettingsQuery.data,
    selectedThreadId,
    setActionError,
    setIsBulkLaunching,
    setIsStreamHealthy,
    threadDetail: threadQuery.data,
    upsertThreadSummary
  });

  async function handleCreateThread() {
    setActionError(null);
    try {
      await createThreadMutation.mutateAsync({});
      requestAnimationFrame(() => {
        runtime.composer.composerTextareaRef.current?.focus();
      });
    } catch (error) {
      setActionError((error as Error).message);
    }
  }

  async function handleDeleteThread(threadId: string) {
    const thread = (displayedThreads ?? []).find((item) => item.id === threadId);
    const threadName = (thread?.title || "").trim() || "Untitled thread";
    if (!window.confirm(`Delete "${threadName}"?\n\nThis removes its full message and run history.`)) {
      return;
    }

    setActionError(null);
    try {
      await deleteThreadMutation.mutateAsync(threadId);
    } catch (error) {
      setActionError((error as Error).message);
    }
  }

  async function handleRenameThread(threadId: string, title: string) {
    setActionError(null);
    try {
      await renameThreadMutation.mutateAsync({ threadId, title });
    } catch (error) {
      setActionError((error as Error).message);
      throw error;
    }
  }

  async function handleApproveItem(payload: {
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

  async function handleRejectItem(payload: {
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

  async function handleReopenItem(payload: {
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
    header: {
      createThread() {
        void handleCreateThread();
      },
      isBulkLaunching,
      isMutating,
      isThreadPanelOpen,
      openReview: () => setIsThreadReviewOpen(true),
      pendingReviewCount,
      reviewProposalCount,
      selectedThreadId,
      threadUsageTotals,
      toggleThreadPanel
    },
    timeline: {
      activeOptimisticEvents: runtime.timeline.activeOptimisticEvents,
      activeOptimisticToolCalls: runtime.timeline.activeOptimisticToolCalls,
      activeStreamReasoningText: runtime.timeline.activeStreamReasoningText,
      activeStreamText: runtime.timeline.activeStreamText,
      errorMessage: threadQuery.isError ? (threadQuery.error as Error).message : null,
      hydratingToolCallIds: runtime.timeline.hydratingToolCallIds,
      isAtBottom: runtime.timeline.isAtBottom,
      isLoading: threadQuery.isLoading,
      isMutating,
      messages: threadQuery.data?.messages,
      onHydrateToolCall: runtime.timeline.onHydrateToolCall,
      optimisticRunEventsByRunId: runtime.timeline.optimisticRunEventsByRunId,
      optimisticToolCallsByRunId: runtime.timeline.optimisticToolCallsByRunId,
      pendingAssistantMessage: runtime.timeline.pendingAssistantMessage,
      pendingAssistantRuns,
      pendingAssistantRunsByUserMessageId,
      pendingRunAttachedToOptimisticMessage: runtime.timeline.pendingRunAttachedToOptimisticMessage,
      pendingUserMessage: runtime.timeline.pendingUserMessage,
      runsByAssistantMessageId,
      scrollToBottom: runtime.timeline.scrollToBottom,
      selectedThreadId,
      shouldShowOptimisticAssistantBubble: runtime.timeline.shouldShowOptimisticAssistantBubble,
      timelineScrollRef: runtime.timeline.timelineScrollRef
    },
    composer: {
      ...runtime.composer
    },
    threadPanel: {
      deletingThreadId: deleteThreadMutation.isPending ? (deleteThreadMutation.variables ?? null) : null,
      errorMessage: threadsQuery.isError ? (threadsQuery.error as Error).message : null,
      handleResizeMouseDown,
      isDeleteDisabled: isMutating || runtime.composer.isRunInFlight || isBulkLaunching,
      isLoading: threadsQuery.isLoading,
      isOpen: isThreadPanelOpen,
      isRenameDisabled: isMutating || runtime.composer.isRunInFlight || isBulkLaunching,
      onDeleteThread(threadId: string) {
        void handleDeleteThread(threadId);
      },
      onRenameThread: handleRenameThread,
      onSelectThread: setSelectedThreadId,
      optimisticRunningThreadIds,
      panelWidth,
      renamingThreadId: renameThreadMutation.isPending ? (renameThreadMutation.variables?.threadId ?? null) : null,
      selectedThreadId,
      slotClassName: isThreadPanelOpen
        ? "agent-thread-panel-slot"
        : "agent-thread-panel-slot agent-thread-panel-slot-collapsed",
      threads: displayedThreads
    },
    reviewModal: {
      isBusy: isMutating,
      onApproveItem: handleApproveItem,
      onOpenChange: setIsThreadReviewOpen,
      onRejectItem: handleRejectItem,
      onReopenItem: handleReopenItem,
      open: isThreadReviewOpen,
      runs: threadQuery.data?.runs ?? []
    },
    previewDialog: runtime.previewDialog
  };
}

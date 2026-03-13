/**
 * CALLING SPEC:
 * - Purpose: provide the `useAgentPanelController` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/features/agent/panel/useAgentPanelController.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `useAgentPanelController`.
 * - Side effects: client-side state coordination and query wiring.
 */
import { useCallback, useState } from "react";

import { useResizablePanel } from "../../../hooks/useResizablePanel";
import { displayThreadName } from "./format";
import { useAgentComposerRuntime } from "./useAgentComposerRuntime";
import { useAgentPanelQueries } from "./useAgentPanelQueries";
import { useAgentThreadActions } from "./useAgentThreadActions";

interface UseAgentPanelControllerArgs {
  isOpen: boolean;
}

export function useAgentPanelController({ isOpen }: UseAgentPanelControllerArgs) {
  const [selectedThreadId, setSelectedThreadId] = useState<string>("");
  const [isThreadReviewOpen, setIsThreadReviewOpen] = useState(false);
  const [isThreadPanelOpen, setIsThreadPanelOpen] = useState(true);
  const [isBulkLaunching, setIsBulkLaunching] = useState(false);
  const [pendingDeleteThread, setPendingDeleteThread] = useState<{ id: string; name: string } | null>(null);
  const [streamHealthyThreadIds, setStreamHealthyThreadIds] = useState<string[]>([]);
  const { panelWidth, handleMouseDown: handleResizeMouseDown } = useResizablePanel({
    storageKey: "agent-thread-panel-width",
    defaultWidth: 300,
    minWidth: 200,
    maxWidth: 600,
    edge: "right"
  });
  const toggleThreadPanel = useCallback(() => setIsThreadPanelOpen((value) => !value), []);
  const setThreadStreamHealthy = useCallback((threadId: string, isHealthy: boolean) => {
    setStreamHealthyThreadIds((current) => {
      if (isHealthy) {
        return current.includes(threadId) ? current : [...current, threadId];
      }
      return current.filter((item) => item !== threadId);
    });
  }, []);

  const actions = useAgentThreadActions({
    selectedThreadId,
    setSelectedThreadId
  });
  const data = useAgentPanelQueries({
    isOpen,
    selectedThreadId,
    setSelectedThreadId,
    optimisticRunningThreadIds: actions.optimisticRunningThreadIds,
    optimisticThreadTitlesById: actions.optimisticThreadTitlesById,
    isBulkLaunching,
    isStreamHealthy: selectedThreadId ? streamHealthyThreadIds.includes(selectedThreadId) : false,
    pruneOptimisticRunningThreadIds: actions.pruneOptimisticRunningThreadIds
  });

  const runtime = useAgentComposerRuntime({
    actionError: actions.actionError,
    addOptimisticRunningThreadId: actions.addOptimisticRunningThreadId,
    applyThreadTitleToCaches: actions.applyThreadTitleToCaches,
    availableComposerModels: data.runtimeSettingsQuery.data?.available_agent_models ?? [],
    clearOptimisticThreadTitle: actions.clearOptimisticThreadTitle,
    ensureThreadId: actions.ensureThreadId,
    async interruptRun(payload: { runId: string; threadId: string }) {
      await actions.interruptRunMutation.mutateAsync(payload);
    },
    isBulkLaunching,
    isInterruptPending:
      actions.interruptRunMutation.isPending && actions.interruptRunMutation.variables?.threadId === selectedThreadId,
    isMutating: actions.isMutating,
    removeOptimisticRunningThreadId: actions.removeOptimisticRunningThreadId,
    runtimeSettings: data.runtimeSettingsQuery.data,
    selectedThreadId,
    setActionError: actions.setActionError,
    setIsBulkLaunching,
    setThreadStreamHealthy,
    threadDetail: data.threadQuery.data,
    upsertThreadSummary: actions.upsertThreadSummary
  });

  async function handleCreateThread() {
    try {
      await actions.createThread();
      requestAnimationFrame(() => {
        runtime.composer.composerTextareaRef.current?.focus();
      });
    } catch (error) {
      actions.setActionError((error as Error).message);
    }
  }

  async function handleDeleteThread(threadId: string) {
    try {
      await actions.deleteThread(threadId);
      setPendingDeleteThread(null);
      setIsThreadReviewOpen(false);
    } catch {
      return;
    }
  }

  function requestDeleteThread(threadId: string) {
    const thread = data.displayedThreads?.find((item) => item.id === threadId);
    actions.deleteThreadMutation.reset();
    setPendingDeleteThread({
      id: threadId,
      name: thread ? displayThreadName(thread) : "Untitled thread"
    });
  }

  function handleDeleteDialogOpenChange(open: boolean) {
    if (actions.deleteThreadMutation.isPending) {
      return;
    }
    if (!open) {
      actions.deleteThreadMutation.reset();
      setPendingDeleteThread(null);
    }
  }

  const runningThreadIds = new Set([
    ...actions.optimisticRunningThreadIds,
    ...(data.displayedThreads ?? []).filter((thread) => thread.has_running_run).map((thread) => thread.id)
  ]);

  return {
    header: {
      createThread() {
        void handleCreateThread();
      },
      isBulkLaunching,
      isMutating: actions.isMutating,
      isThreadPanelOpen,
      openReview: () => setIsThreadReviewOpen(true),
      pendingReviewCount: data.pendingReviewCount,
      reviewProposalCount: data.reviewProposalCount,
      selectedThreadId,
      threadUsageTotals: data.threadUsageTotals,
      toggleThreadPanel
    },
    timeline: {
      activeOptimisticEvents: runtime.timeline.activeOptimisticEvents,
      activeOptimisticToolCalls: runtime.timeline.activeOptimisticToolCalls,
      activeStreamReasoningText: runtime.timeline.activeStreamReasoningText,
      activeStreamText: runtime.timeline.activeStreamText,
      errorMessage: data.threadQuery.isError ? (data.threadQuery.error as Error).message : null,
      hydratingToolCallIds: runtime.timeline.hydratingToolCallIds,
      isAtBottom: runtime.timeline.isAtBottom,
      isLoading: data.threadQuery.isLoading,
      isMutating: actions.isMutating,
      messages: data.threadQuery.data?.messages,
      onHydrateToolCall: runtime.timeline.onHydrateToolCall,
      optimisticRunEventsByRunId: runtime.timeline.optimisticRunEventsByRunId,
      optimisticToolCallsByRunId: runtime.timeline.optimisticToolCallsByRunId,
      pendingAssistantMessage: runtime.timeline.pendingAssistantMessage,
      pendingAssistantRuns: data.pendingAssistantRuns,
      pendingAssistantRunsByUserMessageId: data.pendingAssistantRunsByUserMessageId,
      pendingRunAttachedToOptimisticMessage: runtime.timeline.pendingRunAttachedToOptimisticMessage,
      pendingUserMessage: runtime.timeline.pendingUserMessage,
      runsByAssistantMessageId: data.runsByAssistantMessageId,
      scrollToBottom: runtime.timeline.scrollToBottom,
      selectedThreadId,
      shouldShowOptimisticAssistantBubble: runtime.timeline.shouldShowOptimisticAssistantBubble,
      timelineScrollRef: runtime.timeline.timelineScrollRef
    },
    composer: {
      ...runtime.composer
    },
    threadPanel: {
      deletingThreadId: actions.deleteThreadMutation.isPending ? (actions.deleteThreadMutation.variables ?? null) : null,
      deleteDisabledThreadIds: [
        ...(actions.deleteThreadMutation.isPending && actions.deleteThreadMutation.variables
          ? [actions.deleteThreadMutation.variables]
          : []),
        ...runningThreadIds
      ],
      errorMessage: data.threadsQuery.isError ? (data.threadsQuery.error as Error).message : null,
      handleResizeMouseDown,
      isLoading: data.threadsQuery.isLoading,
      isOpen: isThreadPanelOpen,
      onDeleteThread(threadId: string) {
        requestDeleteThread(threadId);
      },
      onRenameThread: actions.renameThread,
      onSelectThread: setSelectedThreadId,
      optimisticRunningThreadIds: actions.optimisticRunningThreadIds,
      panelWidth,
      renamingThreadId: actions.renameThreadMutation.isPending ? (actions.renameThreadMutation.variables?.threadId ?? null) : null,
      renameDisabledThreadIds:
        actions.renameThreadMutation.isPending && actions.renameThreadMutation.variables?.threadId
          ? [actions.renameThreadMutation.variables.threadId]
          : [],
      selectedThreadId,
      slotClassName: isThreadPanelOpen
        ? "agent-thread-panel-slot"
        : "agent-thread-panel-slot agent-thread-panel-slot-collapsed",
      threads: data.displayedThreads
    },
    reviewModal: {
      isBusy: actions.isMutating,
      onApproveItem: actions.approveItem,
      onOpenChange: setIsThreadReviewOpen,
      onRejectItem: actions.rejectItem,
      onReopenItem: actions.reopenItem,
      open: isThreadReviewOpen,
      runs: data.threadQuery.data?.runs ?? []
    },
    deleteDialog: {
      confirmLabel: "Delete thread",
      description: "This removes the full message and run history for this thread.",
      errorMessage: actions.deleteThreadMutation.isError ? (actions.deleteThreadMutation.error as Error).message : null,
      isPending: actions.deleteThreadMutation.isPending,
      onConfirm() {
        if (!pendingDeleteThread) {
          return;
        }
        void handleDeleteThread(pendingDeleteThread.id);
      },
      onOpenChange: handleDeleteDialogOpenChange,
      open: pendingDeleteThread !== null,
      title: pendingDeleteThread ? `Delete ${pendingDeleteThread.name}?` : "Delete thread?"
    },
    previewDialog: runtime.previewDialog
  };
}

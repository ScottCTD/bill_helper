import { useCallback, useState } from "react";

import { useResizablePanel } from "../../../hooks/useResizablePanel";
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
  const [isStreamHealthy, setIsStreamHealthy] = useState(false);
  const { panelWidth, handleMouseDown: handleResizeMouseDown } = useResizablePanel({
    storageKey: "agent-thread-panel-width",
    defaultWidth: 300,
    minWidth: 200,
    maxWidth: 600,
    edge: "right"
  });
  const toggleThreadPanel = useCallback(() => setIsThreadPanelOpen((value) => !value), []);

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
    isStreamHealthy,
    pruneOptimisticRunningThreadIds: actions.pruneOptimisticRunningThreadIds
  });

  const runtime = useAgentComposerRuntime({
    actionError: actions.actionError,
    addOptimisticRunningThreadId: actions.addOptimisticRunningThreadId,
    applyThreadTitleToCaches: actions.applyThreadTitleToCaches,
    availableComposerModels: data.runtimeSettingsQuery.data?.available_agent_models ?? [],
    clearOptimisticThreadTitle: actions.clearOptimisticThreadTitle,
    ensureThreadId: actions.ensureThreadId,
    async interruptRun(runId: string) {
      await actions.interruptRunMutation.mutateAsync(runId);
    },
    isBulkLaunching,
    isInterruptPending: actions.interruptRunMutation.isPending,
    isMutating: actions.isMutating,
    removeOptimisticRunningThreadId: actions.removeOptimisticRunningThreadId,
    runtimeSettings: data.runtimeSettingsQuery.data,
    selectedThreadId,
    setActionError: actions.setActionError,
    setIsBulkLaunching,
    setIsStreamHealthy,
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
      const deleted = await actions.deleteThread(threadId, data.displayedThreads);
      if (deleted) {
        setIsThreadReviewOpen(false);
      }
    } catch (error) {
      actions.setActionError((error as Error).message);
    }
  }

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
      errorMessage: data.threadsQuery.isError ? (data.threadsQuery.error as Error).message : null,
      handleResizeMouseDown,
      isDeleteDisabled: actions.isMutating || runtime.composer.isRunInFlight || isBulkLaunching,
      isLoading: data.threadsQuery.isLoading,
      isOpen: isThreadPanelOpen,
      isRenameDisabled: actions.isMutating || runtime.composer.isRunInFlight || isBulkLaunching,
      onDeleteThread(threadId: string) {
        void handleDeleteThread(threadId);
      },
      onRenameThread: actions.renameThread,
      onSelectThread: setSelectedThreadId,
      optimisticRunningThreadIds: actions.optimisticRunningThreadIds,
      panelWidth,
      renamingThreadId: actions.renameThreadMutation.isPending ? (actions.renameThreadMutation.variables?.threadId ?? null) : null,
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
    previewDialog: runtime.previewDialog
  };
}

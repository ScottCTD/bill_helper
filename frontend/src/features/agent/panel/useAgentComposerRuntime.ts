import { type ChangeEvent, type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import type { AgentThreadDetail, AgentThreadSummary, RuntimeSettings } from "../../../lib/types";
import { sortRunsByCreatedAt } from "../activity";
import {
  BULK_MODE_HELP_TEXT,
  DEFAULT_BULK_LAUNCH_CONCURRENCY_LIMIT,
  resolveComposerModelName
} from "./helpers";
import { useAgentComposerActions } from "./useAgentComposerActions";
import { useAgentComposerStreamState } from "./useAgentComposerStreamState";
import { useAgentDraftAttachments } from "./useAgentDraftAttachments";
import { useStickToBottom } from "./useStickToBottom";
import {
  COMPOSER_TEXTAREA_MAX_HEIGHT_PX,
  type PendingAssistantMessage,
  type PendingUserMessage
} from "./types";

interface UseAgentComposerRuntimeArgs {
  actionError: string | null;
  addOptimisticRunningThreadId: (threadId: string) => void;
  applyThreadTitleToCaches: (threadId: string, title: string | null, updatedAt?: string) => void;
  availableComposerModels: string[];
  clearOptimisticThreadTitle: (threadId: string) => void;
  ensureThreadId: () => Promise<string>;
  interruptRun: (payload: { runId: string; threadId: string }) => Promise<void>;
  isBulkLaunching: boolean;
  isInterruptPending: boolean;
  isMutating: boolean;
  removeOptimisticRunningThreadId: (threadId: string) => void;
  runtimeSettings: RuntimeSettings | undefined;
  selectedThreadId: string;
  setActionError: (message: string | null) => void;
  setIsBulkLaunching: (value: boolean) => void;
  setThreadStreamHealthy: (threadId: string, isHealthy: boolean) => void;
  threadDetail: AgentThreadDetail | undefined;
  upsertThreadSummary: (thread: AgentThreadSummary) => void;
}

export function useAgentComposerRuntime({
  actionError,
  addOptimisticRunningThreadId,
  applyThreadTitleToCaches,
  availableComposerModels,
  clearOptimisticThreadTitle,
  ensureThreadId,
  interruptRun,
  isBulkLaunching,
  isInterruptPending,
  isMutating,
  removeOptimisticRunningThreadId,
  runtimeSettings,
  selectedThreadId,
  setActionError,
  setIsBulkLaunching,
  setThreadStreamHealthy,
  threadDetail,
  upsertThreadSummary
}: UseAgentComposerRuntimeArgs) {
  const [draftMessage, setDraftMessage] = useState("");
  const [isBulkMode, setIsBulkMode] = useState(false);
  const [pendingUserMessagesByThreadId, setPendingUserMessagesByThreadId] = useState<Record<string, PendingUserMessage>>({});
  const [pendingAssistantMessagesByThreadId, setPendingAssistantMessagesByThreadId] = useState<
    Record<string, PendingAssistantMessage>
  >({});
  const { containerRef: timelineScrollRef, isAtBottom, scrollToBottom, snapToBottom } = useStickToBottom<HTMLDivElement>();
  const composerTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [composerModelOverride, setComposerModelOverride] = useState<string | null>(null);
  const lastSnappedThreadRef = useRef("");
  const pendingUserMessagesRef = useRef<Record<string, PendingUserMessage>>({});
  const attachmentState = useAgentDraftAttachments({ setActionError });
  const {
    draftFiles,
    setDraftFiles,
    draftAttachmentPreviews,
    selectedDraftAttachmentPreview,
    previewAttachmentId,
    setPreviewAttachmentId,
    isComposerDragActive,
    fileInputRef,
    handlers: {
      handleDraftFileSelection,
      handleComposerPaste,
      handleComposerDragEnter,
      handleComposerDragOver,
      handleComposerDragLeave,
      handleComposerDrop,
      removeDraftAttachment
    }
  } = attachmentState;

  const resolvedComposerModel = useMemo(
    () => resolveComposerModelName(availableComposerModels, threadDetail, runtimeSettings),
    [availableComposerModels, runtimeSettings, threadDetail]
  );
  const selectedComposerModel =
    composerModelOverride && availableComposerModels.includes(composerModelOverride) ? composerModelOverride : resolvedComposerModel;
  const bulkLaunchConcurrencyLimit =
    runtimeSettings?.agent_bulk_max_concurrent_threads ?? DEFAULT_BULK_LAUNCH_CONCURRENCY_LIMIT;
  const hasActiveRun = useMemo(() => (threadDetail?.runs ?? []).some((run) => run.status === "running"), [threadDetail?.runs]);
  const activeRunId = useMemo(() => {
    const runs = sortRunsByCreatedAt(threadDetail?.runs ?? []);
    for (let index = runs.length - 1; index >= 0; index -= 1) {
      if (runs[index].status === "running") {
        return runs[index].id;
      }
    }
    return null;
  }, [threadDetail?.runs]);
  const pendingUserMessage = selectedThreadId ? (pendingUserMessagesByThreadId[selectedThreadId] ?? null) : null;
  const pendingAssistantMessage = selectedThreadId ? (pendingAssistantMessagesByThreadId[selectedThreadId] ?? null) : null;

  function setPendingUserMessage(threadId: string, message: PendingUserMessage | null) {
    setPendingUserMessagesByThreadId((current) => {
      const existing = current[threadId];
      if (!message) {
        if (!existing) {
          return current;
        }
        existing.attachments.forEach((attachment) => {
          URL.revokeObjectURL(attachment.url);
        });
        const next = { ...current };
        delete next[threadId];
        return next;
      }
      if (existing && existing.id !== message.id) {
        existing.attachments.forEach((attachment) => {
          URL.revokeObjectURL(attachment.url);
        });
      }
      return {
        ...current,
        [threadId]: message
      };
    });
  }

  function setPendingAssistantMessage(threadId: string, message: PendingAssistantMessage | null) {
    setPendingAssistantMessagesByThreadId((current) => {
      if (!message) {
        if (!(threadId in current)) {
          return current;
        }
        const next = { ...current };
        delete next[threadId];
        return next;
      }
      return {
        ...current,
        [threadId]: message
      };
    });
  }

  useEffect(() => {
    pendingUserMessagesRef.current = pendingUserMessagesByThreadId;
  }, [pendingUserMessagesByThreadId]);

  const streamState = useAgentComposerStreamState({
    applyThreadTitleToCaches,
    pendingAssistantMessage,
    selectedThreadId,
    setActionError,
    threadDetail
  });
  const {
    activeOptimisticEvents,
    activeOptimisticToolCalls,
    activeStreamReasoningText,
    activeStreamRunId,
    activeStreamText,
    handleAgentStreamEvent,
    handleHydrateToolCall,
    hydratingToolCallIds,
    optimisticRunEventsByRunId,
    optimisticToolCallsByRunId,
    pendingRunAttachedToOptimisticMessage,
    resetOptimisticRunState,
    shouldShowOptimisticAssistantBubble
  } = streamState;
  const actions = useAgentComposerActions({
    activeRunId,
    activeStreamRunId,
    addOptimisticRunningThreadId,
    bulkLaunchConcurrencyLimit,
    clearOptimisticThreadTitle,
    draftFiles,
    draftMessage,
    ensureThreadId,
    handleAgentStreamEvent,
    interruptRun,
    isBulkMode,
    removeOptimisticRunningThreadId,
    resetOptimisticRunState,
    selectedComposerModel,
    selectedThreadId,
    setActionError,
    setDraftFiles,
    setDraftMessage,
    setIsBulkLaunching,
    setPendingAssistantMessage,
    setPendingUserMessage,
    setPreviewAttachmentId,
    setThreadStreamHealthy,
    snapToBottom,
    threadDetail,
    upsertThreadSummary
  });
  const isSendingMessage = selectedThreadId ? actions.sendingThreadIds.includes(selectedThreadId) : false;
  const isRunInFlight = isSendingMessage || hasActiveRun;

  function autoSizeComposerTextarea(target?: HTMLTextAreaElement | null) {
    const textarea = target ?? composerTextareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    const nextHeight = Math.min(textarea.scrollHeight, COMPOSER_TEXTAREA_MAX_HEIGHT_PX);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > COMPOSER_TEXTAREA_MAX_HEIGHT_PX ? "auto" : "hidden";
  }

  useEffect(() => {
    setComposerModelOverride(null);
  }, [selectedThreadId]);

  useEffect(() => {
    if (composerModelOverride && !availableComposerModels.includes(composerModelOverride)) {
      setComposerModelOverride(null);
    }
  }, [availableComposerModels, composerModelOverride]);

  useEffect(() => {
    if (!selectedThreadId || !threadDetail?.messages || lastSnappedThreadRef.current === selectedThreadId) {
      return;
    }
    lastSnappedThreadRef.current = selectedThreadId;
    requestAnimationFrame(() => snapToBottom());
  }, [selectedThreadId, snapToBottom, threadDetail?.messages]);

  useEffect(() => {
    autoSizeComposerTextarea();
  }, [draftMessage]);

  useEffect(() => {
    return () => {
      Object.values(pendingUserMessagesRef.current).forEach((message) => {
        message.attachments.forEach((attachment) => {
          URL.revokeObjectURL(attachment.url);
        });
      });
    };
  }, []);

  useEffect(() => {
    if (!pendingUserMessage || pendingUserMessage.threadId !== selectedThreadId) {
      return;
    }
    const latestPersistedUserMessage = [...(threadDetail?.messages ?? [])]
      .reverse()
      .find((message) => message.role === "user");
    if (!latestPersistedUserMessage || latestPersistedUserMessage.id === pendingUserMessage.baselineLastUserMessageId) {
      return;
    }
    setPendingUserMessage(selectedThreadId, null);
  }, [pendingUserMessage, selectedThreadId, threadDetail?.messages]);

  useEffect(() => {
    if (!pendingAssistantMessage || pendingAssistantMessage.threadId !== selectedThreadId) {
      return;
    }
    const latestPersistedAssistantMessage = [...(threadDetail?.messages ?? [])]
      .reverse()
      .find((message) => message.role === "assistant");
    if (
      !latestPersistedAssistantMessage ||
      latestPersistedAssistantMessage.id === pendingAssistantMessage.baselineLastAssistantMessageId
    ) {
      return;
    }
    setPendingAssistantMessage(selectedThreadId, null);
    resetOptimisticRunState(selectedThreadId);
    setThreadStreamHealthy(selectedThreadId, false);
  }, [pendingAssistantMessage, resetOptimisticRunState, selectedThreadId, setThreadStreamHealthy, threadDetail?.messages]);

  useEffect(() => {
    if (
      !pendingAssistantMessage ||
      pendingAssistantMessage.threadId !== selectedThreadId ||
      isRunInFlight ||
      pendingUserMessage
    ) {
      return;
    }
    setPendingAssistantMessage(selectedThreadId, null);
    resetOptimisticRunState(selectedThreadId);
    setThreadStreamHealthy(selectedThreadId, false);
  }, [
    isRunInFlight,
    pendingAssistantMessage,
    pendingUserMessage,
    resetOptimisticRunState,
    selectedThreadId,
    setThreadStreamHealthy
  ]);

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.nativeEvent.isComposing) {
      return;
    }

    const hasMultipleLines = event.currentTarget.value.includes("\n");
    const hasSubmitModifier = event.metaKey || event.ctrlKey;
    const shouldSubmit = hasSubmitModifier || (!hasMultipleLines && !event.shiftKey);
    if (!shouldSubmit) {
      return;
    }

    event.preventDefault();
    if (isMutating || isBulkLaunching || (!isBulkMode && isRunInFlight)) {
      return;
    }
    event.currentTarget.form?.requestSubmit();
  }

  function handleDraftMessageChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setDraftMessage(event.target.value);
    autoSizeComposerTextarea(event.target);
  }

  function handleComposerModelChange(event: ChangeEvent<HTMLSelectElement>) {
    setComposerModelOverride(event.target.value);
  }

  function handleBulkModeChange(checked: boolean) {
    setIsBulkMode(checked);
    setActionError(null);
  }

  return {
    composer: {
      actionError,
      availableModels: availableComposerModels,
      bulkModeHelpText: BULK_MODE_HELP_TEXT,
      composerTextareaRef,
      draftAttachmentPreviews,
      draftMessage,
      fileInputRef,
      isBulkLaunching,
      isBulkMode,
      isComposerDragActive,
      isInterruptPending,
      isModelPickerDisabled: isMutating || isBulkLaunching,
      isMutating,
      isRunInFlight,
      isSendingMessage,
      onBulkModeChange: handleBulkModeChange,
      onComposerKeyDown: handleComposerKeyDown,
      onComposerPaste: handleComposerPaste,
      onDragEnter: handleComposerDragEnter,
      onDragLeave: handleComposerDragLeave,
      onDragOver: handleComposerDragOver,
      onDrop: handleComposerDrop,
      onFileSelection: handleDraftFileSelection,
      onMessageChange: handleDraftMessageChange,
      onModelChange: handleComposerModelChange,
      onRemoveAttachment: removeDraftAttachment,
      onStopRun() {
        void actions.handleStopRun();
      },
      onSubmit: actions.handleSubmitMessage,
      previewAttachmentId,
      selectedModel: selectedComposerModel,
      setPreviewAttachmentId
    },
    previewDialog: {
      onClose() {
        setPreviewAttachmentId(null);
      },
      preview: selectedDraftAttachmentPreview
    },
    timeline: {
      activeOptimisticEvents,
      activeOptimisticToolCalls,
      activeStreamReasoningText,
      activeStreamText,
      hydratingToolCallIds,
      isAtBottom,
      onHydrateToolCall: handleHydrateToolCall,
      optimisticRunEventsByRunId,
      optimisticToolCallsByRunId,
      pendingAssistantMessage,
      pendingRunAttachedToOptimisticMessage,
      pendingUserMessage,
      scrollToBottom,
      shouldShowOptimisticAssistantBubble,
      timelineScrollRef
    }
  };
}

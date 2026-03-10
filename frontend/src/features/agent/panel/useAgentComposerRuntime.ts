import { type ChangeEvent, type FormEvent, type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useNotifications } from "../../../components/ui/notification-center";
import { createAgentThread, deleteAgentThread, getAgentThread, getAgentToolCall, sendAgentMessage, streamAgentMessage } from "../../../lib/api";
import { invalidateAgentThreadData } from "../../../lib/queryInvalidation";
import { queryKeys } from "../../../lib/queryKeys";
import type { AgentRun, AgentRunEvent, AgentStreamEvent, AgentThread, AgentThreadDetail, AgentThreadSummary, AgentToolCall, RuntimeSettings } from "../../../lib/types";
import { mergeRunToolCalls, runsWithoutAssistantMessage, sortRunsByCreatedAt } from "../activity";
import {
  BULK_MODE_HELP_TEXT,
  buildThreadSummary,
  DEFAULT_BULK_LAUNCH_CONCURRENCY_LIMIT,
  deriveThreadTitleFromFilename,
  extractRenameThreadTitle,
  mapWithConcurrency,
  resolveComposerModelName,
  summarizeFilenames
} from "./helpers";
import { useAgentDraftAttachments } from "./useAgentDraftAttachments";
import { useStickToBottom } from "./useStickToBottom";
import {
  COMPOSER_TEXTAREA_MAX_HEIGHT_PX,
  detectDraftAttachmentKind,
  type DraftAttachment,
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
  interruptRun: (runId: string) => Promise<void>;
  isBulkLaunching: boolean;
  isInterruptPending: boolean;
  isMutating: boolean;
  removeOptimisticRunningThreadId: (threadId: string) => void;
  runtimeSettings: RuntimeSettings | undefined;
  selectedThreadId: string;
  setActionError: (message: string | null) => void;
  setIsBulkLaunching: (value: boolean) => void;
  setIsStreamHealthy: (value: boolean) => void;
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
  setIsStreamHealthy,
  threadDetail,
  upsertThreadSummary
}: UseAgentComposerRuntimeArgs) {
  const queryClient = useQueryClient();
  const { notify } = useNotifications();
  const [draftMessage, setDraftMessage] = useState("");
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [isBulkMode, setIsBulkMode] = useState(false);
  const [activeStreamRunId, setActiveStreamRunId] = useState<string | null>(null);
  const [streamedReasoningTextByRunId, setStreamedReasoningTextByRunId] = useState<Record<string, string>>({});
  const [streamedTextByRunId, setStreamedTextByRunId] = useState<Record<string, string>>({});
  const [optimisticRunEventsByRunId, setOptimisticRunEventsByRunId] = useState<Record<string, AgentRunEvent[]>>({});
  const [optimisticToolCallsByRunId, setOptimisticToolCallsByRunId] = useState<Record<string, AgentToolCall[]>>({});
  const [hydratingToolCallIds, setHydratingToolCallIds] = useState<Set<string>>(new Set());
  const [pendingUserMessage, setPendingUserMessage] = useState<PendingUserMessage | null>(null);
  const [pendingAssistantMessage, setPendingAssistantMessage] = useState<PendingAssistantMessage | null>(null);
  const { containerRef: timelineScrollRef, isAtBottom, scrollToBottom, snapToBottom } = useStickToBottom<HTMLDivElement>();
  const composerTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [composerModelOverride, setComposerModelOverride] = useState<string | null>(null);
  const sendAbortControllerRef = useRef<AbortController | null>(null);
  const threadRunsRef = useRef<AgentRun[]>([]);
  const optimisticToolCallsRef = useRef<Record<string, AgentToolCall[]>>({});
  const hydratingToolCallIdsRef = useRef<Set<string>>(new Set());
  const lastSnappedThreadRef = useRef("");
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
  const pendingAssistantRuns = useMemo(() => runsWithoutAssistantMessage(threadDetail), [threadDetail]);
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
  const isRunInFlight = isSendingMessage || hasActiveRun;
  const shouldShowOptimisticAssistantBubble = Boolean(
    pendingAssistantMessage &&
      pendingAssistantMessage.threadId === selectedThreadId
  );
  const pendingRunAttachedToOptimisticMessage = useMemo(() => {
    if (!pendingAssistantMessage || pendingAssistantMessage.threadId !== selectedThreadId) {
      return null;
    }
    if (activeStreamRunId) {
      return (threadDetail?.runs ?? []).find((run) => run.id === activeStreamRunId) ?? null;
    }
    const runningRun = [...pendingAssistantRuns].reverse().find((run) => run.status === "running");
    return runningRun ?? null;
  }, [activeStreamRunId, pendingAssistantMessage, pendingAssistantRuns, selectedThreadId, threadDetail?.runs]);
  const activeStreamText = useMemo(
    () => (activeStreamRunId ? streamedTextByRunId[activeStreamRunId] ?? "" : ""),
    [activeStreamRunId, streamedTextByRunId]
  );
  const activeStreamReasoningText = useMemo(
    () => (activeStreamRunId ? streamedReasoningTextByRunId[activeStreamRunId] ?? "" : ""),
    [activeStreamRunId, streamedReasoningTextByRunId]
  );
  const activeOptimisticEvents = useMemo(
    () => (activeStreamRunId ? optimisticRunEventsByRunId[activeStreamRunId] ?? [] : []),
    [activeStreamRunId, optimisticRunEventsByRunId]
  );
  const activeOptimisticToolCalls = useMemo(
    () => (activeStreamRunId ? optimisticToolCallsByRunId[activeStreamRunId] ?? [] : []),
    [activeStreamRunId, optimisticToolCallsByRunId]
  );

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

  const resetOptimisticRunState = useCallback(() => {
    setActiveStreamRunId(null);
    setStreamedReasoningTextByRunId({});
    setStreamedTextByRunId({});
    setOptimisticRunEventsByRunId({});
    setOptimisticToolCallsByRunId({});
    setHydratingToolCallIds(new Set());
    hydratingToolCallIdsRef.current.clear();
  }, []);

  useEffect(() => {
    setComposerModelOverride(null);
  }, [selectedThreadId]);

  useEffect(() => {
    if (composerModelOverride && !availableComposerModels.includes(composerModelOverride)) {
      setComposerModelOverride(null);
    }
  }, [availableComposerModels, composerModelOverride]);

  useEffect(() => {
    threadRunsRef.current = threadDetail?.runs ?? [];
  }, [threadDetail?.runs]);

  useEffect(() => {
    optimisticToolCallsRef.current = optimisticToolCallsByRunId;
  }, [optimisticToolCallsByRunId]);

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
    if (!pendingUserMessage) {
      return;
    }
    return () => {
      pendingUserMessage.attachments.forEach((attachment) => {
        URL.revokeObjectURL(attachment.url);
      });
    };
  }, [pendingUserMessage]);

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
    setPendingUserMessage(null);
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
    setPendingAssistantMessage(null);
    resetOptimisticRunState();
    setIsStreamHealthy(false);
  }, [pendingAssistantMessage, resetOptimisticRunState, selectedThreadId, setIsStreamHealthy, threadDetail?.messages]);

  useEffect(() => {
    return () => {
      if (sendAbortControllerRef.current) {
        sendAbortControllerRef.current.abort();
        sendAbortControllerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    setPendingAssistantMessage(null);
    resetOptimisticRunState();
    setIsStreamHealthy(false);
  }, [resetOptimisticRunState, selectedThreadId, setIsStreamHealthy]);

  useEffect(() => {
    if (
      !pendingAssistantMessage ||
      pendingAssistantMessage.threadId !== selectedThreadId ||
      isRunInFlight ||
      pendingUserMessage
    ) {
      return;
    }
    setPendingAssistantMessage(null);
    resetOptimisticRunState();
    setIsStreamHealthy(false);
  }, [isRunInFlight, pendingAssistantMessage, pendingUserMessage, resetOptimisticRunState, selectedThreadId, setIsStreamHealthy]);

  const hydrateToolCallDetails = useCallback(
    async (threadId: string, runId: string, toolCallId: string, force = false) => {
      const persistedRun = threadRunsRef.current.find((run) => run.id === runId);
      if (!force && persistedRun?.tool_calls.some((toolCall) => toolCall.id === toolCallId && toolCall.has_full_payload)) {
        return;
      }

      const optimisticToolCalls = optimisticToolCallsRef.current[runId] ?? [];
      if (!force && optimisticToolCalls.some((toolCall) => toolCall.id === toolCallId && toolCall.has_full_payload)) {
        return;
      }

      if (hydratingToolCallIdsRef.current.has(toolCallId)) {
        return;
      }

      hydratingToolCallIdsRef.current.add(toolCallId);
      setHydratingToolCallIds((current) => {
        const next = new Set(current);
        next.add(toolCallId);
        return next;
      });
      try {
        const toolCall = await getAgentToolCall(toolCallId);
        const renamedTitle = toolCall.tool_name === "rename_thread" ? extractRenameThreadTitle(toolCall) : null;
        setOptimisticToolCallsByRunId((current) => {
          const existing = current[runId] ?? [];
          const nextToolCalls = mergeRunToolCalls(existing, [toolCall]);
          if (
            existing.length === nextToolCalls.length &&
            existing.every((existingToolCall, index) => {
              const nextToolCall = nextToolCalls[index];
              return (
                nextToolCall &&
                existingToolCall.id === nextToolCall.id &&
                existingToolCall.status === nextToolCall.status &&
                existingToolCall.has_full_payload === nextToolCall.has_full_payload
              );
            })
          ) {
            return current;
          }
          return {
            ...current,
            [runId]: nextToolCalls
          };
        });
        if (renamedTitle) {
          applyThreadTitleToCaches(threadId, renamedTitle);
        }
      } catch {
        // Ignore transient hydration errors; later expansions or final snapshots will retry/reconcile.
      } finally {
        hydratingToolCallIdsRef.current.delete(toolCallId);
        setHydratingToolCallIds((current) => {
          if (!current.has(toolCallId)) {
            return current;
          }
          const next = new Set(current);
          next.delete(toolCallId);
          return next;
        });
      }
    },
    [applyThreadTitleToCaches]
  );

  const handleHydrateToolCall = useCallback(
    (runId: string, toolCallId: string) => {
      if (!selectedThreadId) {
        return;
      }
      void hydrateToolCallDetails(selectedThreadId, runId, toolCallId);
    },
    [hydrateToolCallDetails, selectedThreadId]
  );

  function handleAgentStreamEvent(threadId: string, event: AgentStreamEvent) {
    if (event.type === "run_event") {
      setActiveStreamRunId((current) => current || event.run_id);
      const toolCall = event.tool_call;
      if (toolCall) {
        setOptimisticToolCallsByRunId((current) => ({
          ...current,
          [event.run_id]: mergeRunToolCalls(current[event.run_id] ?? [], [toolCall])
        }));
        if (toolCall.tool_name === "rename_thread") {
          if (event.event.event_type === "tool_call_started") {
            void hydrateToolCallDetails(threadId, event.run_id, toolCall.id);
          }
          if (event.event.event_type === "tool_call_completed") {
            void hydrateToolCallDetails(threadId, event.run_id, toolCall.id, true);
          }
          if (event.event.event_type === "tool_call_failed") {
            invalidateAgentThreadData(queryClient, threadId);
          }
        }
      }
      setOptimisticRunEventsByRunId((current) => {
        const existing = current[event.run_id] ?? [];
        if (existing.some((item) => item.id === event.event.id)) {
          return current;
        }
        return {
          ...current,
          [event.run_id]: [...existing, event.event]
        };
      });
      if (event.event.event_type === "reasoning_update" && event.event.source === "assistant_content") {
        setStreamedTextByRunId((current) => {
          if (!current[event.run_id]) {
            return current;
          }
          return {
            ...current,
            [event.run_id]: ""
          };
        });
      }
      if (event.event.event_type === "reasoning_update" && event.event.source === "model_reasoning") {
        setStreamedReasoningTextByRunId((current) => {
          if (!current[event.run_id]) {
            return current;
          }
          return {
            ...current,
            [event.run_id]: ""
          };
        });
      }
      if (event.event.event_type === "run_failed" && event.event.message) {
        setActionError(event.event.message);
      }
      return;
    }
    if (event.type === "reasoning_delta") {
      setActiveStreamRunId((current) => current || event.run_id);
      setStreamedReasoningTextByRunId((current) => ({
        ...current,
        [event.run_id]: `${current[event.run_id] ?? ""}${event.delta}`
      }));
      return;
    }
    if (event.type === "text_delta") {
      setActiveStreamRunId((current) => current || event.run_id);
      setStreamedTextByRunId((current) => ({
        ...current,
        [event.run_id]: `${current[event.run_id] ?? ""}${event.delta}`
      }));
    }
  }

  async function handleSubmitBulkMessages(content: string, attachments: DraftAttachment[]) {
    if (attachments.length === 0) {
      setActionError("Attach at least one file to start Bulk mode.");
      return;
    }

    setActionError(null);
    setIsBulkLaunching(true);
    try {
      const results = await mapWithConcurrency(attachments, bulkLaunchConcurrencyLimit, async (attachment) => {
        let createdThread: AgentThread | null = null;
        try {
          createdThread = await createAgentThread({
            title: deriveThreadTitleFromFilename(attachment.file.name)
          });
          upsertThreadSummary(buildThreadSummary(createdThread));
          addOptimisticRunningThreadId(createdThread.id);
          upsertThreadSummary(
            buildThreadSummary(createdThread, {
              last_message_preview: content || "User sent attachments.",
              has_running_run: true
            })
          );
          await sendAgentMessage({
            threadId: createdThread.id,
            content,
            files: [attachment.file],
            modelName: selectedComposerModel || undefined
          });
          return { attachmentId: attachment.id, fileName: attachment.file.name, failed: false as const, errorMessage: null };
        } catch (error) {
          if (createdThread) {
            removeOptimisticRunningThreadId(createdThread.id);
            try {
              await deleteAgentThread(createdThread.id);
              queryClient.setQueryData(queryKeys.agent.threads, (current: AgentThreadSummary[] | undefined) =>
                (current ?? []).filter((thread) => thread.id !== createdThread?.id)
              );
              queryClient.removeQueries({ queryKey: queryKeys.agent.thread(createdThread.id), exact: true });
            } catch {
              upsertThreadSummary(
                buildThreadSummary(createdThread, {
                  last_message_preview: null,
                  has_running_run: false
                })
              );
            }
          }
          return {
            attachmentId: attachment.id,
            fileName: attachment.file.name,
            failed: true as const,
            errorMessage: (error as Error).message
          };
        }
      });

      const startedCount = results.filter((result) => !result.failed).length;
      const failedResults = results.filter((result) => result.failed);
      const failedAttachmentIdSet = new Set(failedResults.map((result) => result.attachmentId));
      const uniqueErrorMessages = [...new Set(failedResults.map((result) => result.errorMessage).filter(Boolean))];
      setDraftFiles((current) => current.filter((attachment) => failedAttachmentIdSet.has(attachment.id)));
      setPreviewAttachmentId(null);
      if (failedAttachmentIdSet.size === 0) {
        setDraftMessage("");
      }
      setActionError(uniqueErrorMessages.length === 0 ? null : uniqueErrorMessages.join(" "));
      if (failedResults.length === 0) {
        notify({
          title: `Started ${startedCount} thread${startedCount === 1 ? "" : "s"}.`,
          tone: "success"
        });
      } else {
        const descriptionParts = [`Files: ${summarizeFilenames(failedResults.map((result) => result.fileName))}`];
        if (uniqueErrorMessages[0]) {
          descriptionParts.push(uniqueErrorMessages[0]);
        }
        notify({
          title: `Started ${startedCount} thread${startedCount === 1 ? "" : "s"}. Failed ${failedResults.length}.`,
          description: descriptionParts.join(" "),
          tone: "error",
          durationMs: 5600
        });
      }
      invalidateAgentThreadData(queryClient);
    } finally {
      setIsBulkLaunching(false);
    }
  }

  async function handleSubmitSingleMessage(content: string, attachments: DraftAttachment[]) {
    const sendingDraftFiles = [...attachments];
    let threadId: string | null = null;
    try {
      threadId = await ensureThreadId();
      const activeThreadId = threadId;
      const sendAbortController = new AbortController();
      sendAbortControllerRef.current = sendAbortController;
      setIsSendingMessage(true);
      addOptimisticRunningThreadId(activeThreadId);
      setIsStreamHealthy(true);
      resetOptimisticRunState();
      invalidateAgentThreadData(queryClient, activeThreadId);
      const baselineLastUserMessageId =
        [...(threadDetail?.messages ?? [])]
          .reverse()
          .find((message) => message.role === "user")
          ?.id ?? null;
      const baselineLastAssistantMessageId =
        [...(threadDetail?.messages ?? [])]
          .reverse()
          .find((message) => message.role === "assistant")
          ?.id ?? null;
      const optimisticMessage: PendingUserMessage = {
        id: `pending-user-${Date.now()}`,
        threadId: activeThreadId,
        content,
        createdAt: new Date().toISOString(),
        baselineLastUserMessageId,
        attachments: sendingDraftFiles.map((item, index) => ({
          id: `${item.id}-${index}`,
          name: item.file.name,
          url: URL.createObjectURL(item.file),
          mimeType: item.file.type || "",
          kind: detectDraftAttachmentKind(item.file)
        }))
      };
      setPendingUserMessage(optimisticMessage);
      setPendingAssistantMessage({
        id: `pending-assistant-${Date.now()}`,
        threadId: activeThreadId,
        createdAt: new Date().toISOString(),
        baselineLastAssistantMessageId
      });
      setDraftMessage("");
      setDraftFiles([]);
      setPreviewAttachmentId(null);
      snapToBottom();

      await streamAgentMessage({
        threadId: activeThreadId,
        content,
        files: sendingDraftFiles.map((item) => item.file),
        modelName: selectedComposerModel || undefined,
        signal: sendAbortController.signal,
        onEvent: (streamEvent) => handleAgentStreamEvent(activeThreadId, streamEvent)
      });
      sendAbortControllerRef.current = null;
      setIsStreamHealthy(false);
      const detail = await getAgentThread(activeThreadId);
      queryClient.setQueryData(queryKeys.agent.thread(activeThreadId), detail);
      clearOptimisticThreadTitle(activeThreadId);
      invalidateAgentThreadData(queryClient, activeThreadId);
      setPendingUserMessage((current) => (current && current.threadId === activeThreadId ? null : current));
      setPendingAssistantMessage((current) => (current && current.threadId === activeThreadId ? null : current));
      removeOptimisticRunningThreadId(activeThreadId);
      resetOptimisticRunState();
    } catch (error) {
      sendAbortControllerRef.current = null;
      setIsStreamHealthy(false);
      if ((error as Error).name === "AbortError") {
        setPendingUserMessage((current) => (current ? null : current));
        setActionError(null);
      } else {
        setActionError((error as Error).message);
      }
    } finally {
      if (threadId) {
        removeOptimisticRunningThreadId(threadId);
      }
      setIsSendingMessage(false);
    }
  }

  async function handleSubmitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionError(null);
    const content = draftMessage.trim();
    if (isBulkMode) {
      await handleSubmitBulkMessages(content, [...draftFiles]);
      return;
    }
    if (!content && draftFiles.length === 0) {
      setActionError("Enter a message or attach at least one file.");
      return;
    }
    await handleSubmitSingleMessage(content, [...draftFiles]);
  }

  async function handleStopRun() {
    setActionError(null);
    setIsSendingMessage(false);
    setIsStreamHealthy(false);
    if (selectedThreadId) {
      removeOptimisticRunningThreadId(selectedThreadId);
    }
    setPendingAssistantMessage(null);
    resetOptimisticRunState();
    if (sendAbortControllerRef.current) {
      sendAbortControllerRef.current.abort();
      sendAbortControllerRef.current = null;
    }
    let runIdToInterrupt = activeRunId || activeStreamRunId || null;
    if (!runIdToInterrupt && selectedThreadId) {
      try {
        const detail = await getAgentThread(selectedThreadId);
        const latestRunningRun = sortRunsByCreatedAt(detail.runs)
          .reverse()
          .find((run) => run.status === "running");
        runIdToInterrupt = latestRunningRun?.id ?? null;
      } catch {
        runIdToInterrupt = null;
      }
    }
    if (!runIdToInterrupt) {
      return;
    }
    try {
      await interruptRun(runIdToInterrupt);
    } catch (error) {
      setActionError((error as Error).message);
    }
  }

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
        void handleStopRun();
      },
      onSubmit: handleSubmitMessage,
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

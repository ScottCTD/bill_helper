import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PanelRight, PanelRightClose } from "lucide-react";

import {
  approveAgentChangeItem,
  createAgentThread,
  deleteAgentThread,
  getAgentThread,
  interruptAgentRun,
  listAgentThreads,
  rejectAgentChangeItem,
  streamAgentMessage
} from "../../lib/api";
import { invalidateAgentThreadData, invalidateEntryReadModels } from "../../lib/queryInvalidation";
import { queryKeys } from "../../lib/queryKeys";
import type { AgentChangeItem, AgentStreamEvent, AgentThreadDetail, AgentThreadSummary } from "../../lib/types";
import {
  appendPendingReasoningUpdateToActivity,
  appendPendingToolCallToActivity,
  buildThreadUsageTotals,
  runsByAssistantMessage,
  runsWithoutAssistantMessage,
  sortRunsByCreatedAt
} from "./activity";
import { AgentComposer } from "./panel/AgentComposer";
import { AgentAttachmentPreviewDialog } from "./panel/AgentAttachmentPreviewDialog";
import { AgentThreadPanel } from "./panel/AgentThreadPanel";
import { AgentThreadUsageBar } from "./panel/AgentThreadUsageBar";
import { AgentTimeline } from "./panel/AgentTimeline";
import { useStickToBottom } from "./panel/useStickToBottom";
import { useResizablePanel } from "./panel/useResizablePanel";
import { useAgentDraftAttachments } from "./panel/useAgentDraftAttachments";
import {
  COMPOSER_TEXTAREA_MAX_HEIGHT_PX,
  detectDraftAttachmentKind,
  type PendingAssistantMessage,
  type PendingUserMessage
} from "./panel/types";
import { AgentRunReviewModal } from "./review/AgentRunReviewModal";
import { Button } from "../ui/button";

interface AgentPanelProps {
  isOpen: boolean;
  onClose?: () => void;
}

export function AgentPanel({ isOpen, onClose }: AgentPanelProps) {
  const queryClient = useQueryClient();
  const [selectedThreadId, setSelectedThreadId] = useState<string>("");
  const [draftMessage, setDraftMessage] = useState("");
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [isSendPolling, setIsSendPolling] = useState(false);
  const [pendingUserMessage, setPendingUserMessage] = useState<PendingUserMessage | null>(null);
  const [pendingAssistantMessage, setPendingAssistantMessage] = useState<PendingAssistantMessage | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [reviewRunId, setReviewRunId] = useState<string | null>(null);
  const timelineScrollRef = useRef<HTMLDivElement | null>(null);
  const { isAtBottom, scrollToBottom, snapToBottom } = useStickToBottom(timelineScrollRef);
  const composerTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const sendAbortControllerRef = useRef<AbortController | null>(null);
  const [isThreadPanelOpen, setIsThreadPanelOpen] = useState(true);
  const { panelWidth, handleMouseDown: handleResizeMouseDown } = useResizablePanel();
  const toggleThreadPanel = useCallback(() => setIsThreadPanelOpen((v) => !v), []);
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

  const threadsQuery = useQuery({
    queryKey: queryKeys.agent.threads,
    queryFn: listAgentThreads,
    enabled: isOpen
  });

  const threadQuery = useQuery({
    queryKey: queryKeys.agent.thread(selectedThreadId),
    queryFn: () => getAgentThread(selectedThreadId),
    enabled: isOpen && Boolean(selectedThreadId),
    refetchInterval: (query) => {
      const detail = query.state.data as AgentThreadDetail | undefined;
      const hasRunningRun = (detail?.runs ?? []).some((run) => run.status === "running");
      return hasRunningRun || isSendPolling ? 400 : false;
    },
    refetchIntervalInBackground: true
  });

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    if (selectedThreadId) {
      return;
    }
    const firstId = threadsQuery.data?.[0]?.id;
    if (firstId) {
      setSelectedThreadId(firstId);
    }
  }, [isOpen, selectedThreadId, threadsQuery.data]);

  const threadMessages = threadQuery.data?.messages;
  const lastSnappedThreadRef = useRef("");

  // Snap to bottom when messages first arrive for a new thread
  useEffect(() => {
    if (!selectedThreadId || !threadMessages) {
      return;
    }
    if (lastSnappedThreadRef.current === selectedThreadId) {
      return;
    }
    lastSnappedThreadRef.current = selectedThreadId;
    requestAnimationFrame(() => snapToBottom());
  }, [selectedThreadId, threadMessages, snapToBottom]);

  useEffect(() => {
    autoSizeComposerTextarea();
  }, [draftMessage]);

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
      setReviewRunId(null);
      setPendingUserMessage(null);
      setPendingAssistantMessage(null);
      setActionError(null);
      invalidateAgentThreadData(queryClient);
    }
  });

  const interruptRunMutation = useMutation({
    mutationFn: interruptAgentRun,
    onSuccess: () => {
      invalidateAgentThreadData(queryClient, selectedThreadId || undefined);
      setIsSendPolling(false);
      setPendingAssistantMessage(null);
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

  const isMutating =
    createThreadMutation.isPending ||
    deleteThreadMutation.isPending ||
    interruptRunMutation.isPending ||
    approveMutation.isPending ||
    rejectMutation.isPending;

  const runsByAssistantMessageId = useMemo(() => runsByAssistantMessage(threadQuery.data), [threadQuery.data]);
  const pendingAssistantRuns = useMemo(() => runsWithoutAssistantMessage(threadQuery.data), [threadQuery.data]);
  const hasActiveRun = useMemo(
    () => (threadQuery.data?.runs ?? []).some((run) => run.status === "running"),
    [threadQuery.data?.runs]
  );
  const activeRunId = useMemo(() => {
    const runs = sortRunsByCreatedAt(threadQuery.data?.runs ?? []);
    for (let index = runs.length - 1; index >= 0; index -= 1) {
      if (runs[index].status === "running") {
        return runs[index].id;
      }
    }
    return null;
  }, [threadQuery.data?.runs]);
  const isRunInFlight = isSendingMessage || hasActiveRun;
  const shouldShowOptimisticAssistantBubble = Boolean(
    pendingAssistantMessage &&
      pendingAssistantMessage.threadId === selectedThreadId
  );
  const pendingRunAttachedToOptimisticMessage = useMemo(() => {
    if (!pendingAssistantMessage) {
      return null;
    }
    if (pendingAssistantMessage.threadId !== selectedThreadId) {
      return null;
    }
    if (pendingAssistantMessage.runId) {
      return pendingAssistantRuns.find((run) => run.id === pendingAssistantMessage.runId) ?? null;
    }
    const runningRun = [...pendingAssistantRuns].reverse().find((run) => run.status === "running");
    return runningRun ?? null;
  }, [pendingAssistantMessage, pendingAssistantRuns, selectedThreadId]);
  const pendingOptimisticActivity = useMemo(() => {
    if (!pendingAssistantMessage || pendingAssistantMessage.threadId !== selectedThreadId) {
      return [];
    }
    return pendingAssistantMessage.activity;
  }, [pendingAssistantMessage, selectedThreadId]);
  const selectedRunForReview = useMemo(() => {
    if (!reviewRunId) {
      return null;
    }
    return (threadQuery.data?.runs ?? []).find((run) => run.id === reviewRunId) ?? null;
  }, [reviewRunId, threadQuery.data?.runs]);

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
    if (!pendingUserMessage) {
      return;
    }
    if (pendingUserMessage.threadId !== selectedThreadId) {
      return;
    }
    const latestPersistedUserMessage = [...(threadQuery.data?.messages ?? [])]
      .reverse()
      .find((message) => message.role === "user");
    if (!latestPersistedUserMessage) {
      return;
    }
    if (latestPersistedUserMessage.id === pendingUserMessage.baselineLastUserMessageId) {
      return;
    }
    setPendingUserMessage(null);
  }, [pendingUserMessage, selectedThreadId, threadQuery.data?.messages]);

  useEffect(() => {
    if (!pendingAssistantMessage) {
      return;
    }
    if (pendingAssistantMessage.threadId !== selectedThreadId) {
      return;
    }
    const latestPersistedAssistantMessage = [...(threadQuery.data?.messages ?? [])]
      .reverse()
      .find((message) => message.role === "assistant");
    if (!latestPersistedAssistantMessage) {
      return;
    }
    if (latestPersistedAssistantMessage.id === pendingAssistantMessage.baselineLastAssistantMessageId) {
      return;
    }
    setPendingAssistantMessage(null);
  }, [pendingAssistantMessage, selectedThreadId, threadQuery.data?.messages]);

  const activeModelName = useMemo(() => {
    const runs = threadQuery.data?.runs ?? [];
    const latest = runs[runs.length - 1];
    const runModelName = latest?.model_name?.trim();
    if (runModelName) {
      return runModelName;
    }
    const configuredModelName = threadQuery.data?.configured_model_name?.trim();
    return configuredModelName || "unknown model";
  }, [threadQuery.data?.runs, threadQuery.data?.configured_model_name]);

  const threadUsageTotals = useMemo(() => {
    return buildThreadUsageTotals(threadQuery.data);
  }, [threadQuery.data]);

  useEffect(() => {
    return () => {
      if (sendAbortControllerRef.current) {
        sendAbortControllerRef.current.abort();
        sendAbortControllerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    setReviewRunId(null);
    setPendingAssistantMessage(null);
  }, [selectedThreadId]);

  useEffect(() => {
    if (!pendingAssistantMessage) {
      return;
    }
    if (pendingAssistantMessage.threadId !== selectedThreadId) {
      return;
    }
    if (!isRunInFlight && !pendingUserMessage) {
      setPendingAssistantMessage(null);
    }
  }, [isRunInFlight, pendingAssistantMessage, pendingUserMessage, selectedThreadId]);

  useEffect(() => {
    if (!reviewRunId) {
      return;
    }
    if (selectedRunForReview) {
      return;
    }
    setReviewRunId(null);
  }, [reviewRunId, selectedRunForReview]);

  async function handleCreateThread() {
    setActionError(null);
    try {
      await createThreadMutation.mutateAsync({});
      requestAnimationFrame(() => {
        composerTextareaRef.current?.focus();
      });
    } catch (error) {
      setActionError((error as Error).message);
    }
  }

  async function handleDeleteThread(threadId: string) {
    const thread = (threadsQuery.data ?? []).find((item) => item.id === threadId);
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

  async function ensureThreadId(): Promise<string> {
    if (selectedThreadId) {
      return selectedThreadId;
    }
    const created = await createThreadMutation.mutateAsync({});
    setSelectedThreadId(created.id);
    return created.id;
  }

  function handleAgentStreamEvent(threadId: string, event: AgentStreamEvent) {
    const streamEvent = event as AgentStreamEvent & {
      type?: string;
      run_id?: string;
      delta?: string;
      tool_name?: string;
      message?: string;
      error_text?: string | null;
    };
    const eventType = String(streamEvent.type || "");

    if (eventType === "run_started") {
      setPendingAssistantMessage((current) => {
        if (!current || current.threadId !== threadId) {
          return current;
        }
        return { ...current, runId: streamEvent.run_id || current.runId };
      });
      return;
    }
    if (eventType === "tool_call") {
      setPendingAssistantMessage((current) => {
        if (!current || current.threadId !== threadId) {
          return current;
        }
        return {
          ...current,
          runId: current.runId || streamEvent.run_id || null,
          activity: appendPendingToolCallToActivity(current.activity, String(streamEvent.tool_name || ""))
        };
      });
      return;
    }
    if (eventType === "reasoning_update" || eventType === "reasoning") {
      const source = (streamEvent as Record<string, unknown>).source as string | undefined;
      const normalizedSource =
        source === "model_reasoning" || source === "assistant_content" || source === "tool_call"
          ? source
          : "tool_call";
      setPendingAssistantMessage((current) => {
        if (!current || current.threadId !== threadId) {
          return current;
        }
        return {
          ...current,
          runId: current.runId || streamEvent.run_id || null,
          content: "",
          activity: appendPendingReasoningUpdateToActivity(current.activity, String(streamEvent.message || ""), normalizedSource)
        };
      });
      return;
    }
    if (eventType === "text_delta") {
      setPendingAssistantMessage((current) => {
        if (!current || current.threadId !== threadId) {
          return current;
        }
        return {
          ...current,
          runId: current.runId || streamEvent.run_id || null,
          content: `${current.content}${String(streamEvent.delta || "")}`
        };
      });
      return;
    }
    if (eventType === "run_failed" && streamEvent.error_text) {
      setActionError(streamEvent.error_text);
    }
  }

  async function handleSubmitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionError(null);
    const content = draftMessage.trim();
    if (!content && draftFiles.length === 0) {
      setActionError("Enter a message or attach at least one file.");
      return;
    }
    const sendingDraftFiles = [...draftFiles];
    try {
      const threadId = await ensureThreadId();
      const sendAbortController = new AbortController();
      sendAbortControllerRef.current = sendAbortController;
      setIsSendingMessage(true);
      setIsSendPolling(true);
      invalidateAgentThreadData(queryClient, threadId);
      const baselineLastUserMessageId =
        [...(threadQuery.data?.messages ?? [])]
          .reverse()
          .find((message) => message.role === "user")
          ?.id ?? null;
      const baselineLastAssistantMessageId =
        [...(threadQuery.data?.messages ?? [])]
          .reverse()
          .find((message) => message.role === "assistant")
          ?.id ?? null;
      const optimisticMessage: PendingUserMessage = {
        id: `pending-user-${Date.now()}`,
        threadId,
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
        threadId,
        createdAt: new Date().toISOString(),
        content: "",
        runId: null,
        baselineLastAssistantMessageId,
        activity: []
      });
      setDraftMessage("");
      setDraftFiles([]);
      setPreviewAttachmentId(null);
      snapToBottom();

      await streamAgentMessage({
        threadId,
        content: draftMessage,
        files: sendingDraftFiles.map((item) => item.file),
        signal: sendAbortController.signal,
        onEvent: (streamEvent) => handleAgentStreamEvent(threadId, streamEvent)
      });
      sendAbortControllerRef.current = null;
      const detail = await getAgentThread(threadId);
      queryClient.setQueryData(queryKeys.agent.thread(threadId), detail);
      invalidateAgentThreadData(queryClient, threadId);
      setPendingUserMessage((current) => {
        if (!current || current.threadId !== threadId) {
          return current;
        }
        return null;
      });
      setPendingAssistantMessage((current) => {
        if (!current || current.threadId !== threadId) {
          return current;
        }
        return null;
      });
    } catch (error) {
      sendAbortControllerRef.current = null;
      setPendingUserMessage((current) => {
        return current ? null : current;
      });
      setPendingAssistantMessage(null);
      if ((error as Error).name === "AbortError") {
        setActionError(null);
      } else {
        setActionError((error as Error).message);
      }
    } finally {
      setIsSendingMessage(false);
      setIsSendPolling(false);
    }
  }

  async function handleStopRun() {
    setActionError(null);
    setIsSendingMessage(false);
    setIsSendPolling(false);
    setPendingAssistantMessage(null);
    if (sendAbortControllerRef.current) {
      sendAbortControllerRef.current.abort();
      sendAbortControllerRef.current = null;
    }
    let runIdToInterrupt = activeRunId || pendingAssistantMessage?.runId || null;
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
      await interruptRunMutation.mutateAsync(runIdToInterrupt);
    } catch (error) {
      setActionError((error as Error).message);
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter") {
      return;
    }
    if (event.nativeEvent.isComposing) {
      return;
    }

    const hasMultipleLines = event.currentTarget.value.includes("\n");
    const hasSubmitModifier = event.metaKey || event.ctrlKey;
    const shouldSubmit = hasSubmitModifier || (!hasMultipleLines && !event.shiftKey);
    if (!shouldSubmit) {
      return;
    }

    event.preventDefault();
    if (isMutating || isRunInFlight) {
      return;
    }
    event.currentTarget.form?.requestSubmit();
  }

  function handleDraftMessageChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setDraftMessage(event.target.value);
    autoSizeComposerTextarea(event.target);
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
      setActionError((error as Error).message);
      throw error;
    }
  }

  async function handleRejectItem(payload: { itemId: string }): Promise<AgentChangeItem> {
    setActionError(null);
    try {
      return await rejectMutation.mutateAsync({ itemId: payload.itemId });
    } catch (error) {
      setActionError((error as Error).message);
      throw error;
    }
  }

  if (!isOpen) {
    return null;
  }

  return (
    <>
      <aside className="agent-panel agent-panel-page" aria-label="Agent panel">
        <header className="agent-panel-header">
          <h2>{`Agent (${activeModelName})`}</h2>
          <AgentThreadUsageBar selectedThreadId={selectedThreadId} totals={threadUsageTotals} />
          <div className="agent-panel-header-actions">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                void handleCreateThread();
              }}
              disabled={isMutating}
            >
              New Thread
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={toggleThreadPanel}
              title={isThreadPanelOpen ? "Collapse threads" : "Expand threads"}
            >
              {isThreadPanelOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRight className="h-4 w-4" />}
            </Button>
          </div>
        </header>

        <div className="agent-panel-body agent-panel-body-page">
          <section className="agent-thread-timeline agent-thread-main">
            <AgentTimeline
              selectedThreadId={selectedThreadId}
              isLoading={threadQuery.isLoading}
              errorMessage={threadQuery.isError ? (threadQuery.error as Error).message : null}
              messages={threadQuery.data?.messages}
              timelineScrollRef={timelineScrollRef}
              runsByAssistantMessageId={runsByAssistantMessageId}
              pendingAssistantRuns={pendingAssistantRuns}
              pendingUserMessage={pendingUserMessage}
              pendingAssistantMessage={pendingAssistantMessage}
              shouldShowOptimisticAssistantBubble={shouldShowOptimisticAssistantBubble}
              pendingRunAttachedToOptimisticMessage={pendingRunAttachedToOptimisticMessage}
              isMutating={isMutating}
              pendingOptimisticActivityCount={pendingOptimisticActivity.length}
              onReviewRun={setReviewRunId}
              isAtBottom={isAtBottom}
              scrollToBottom={scrollToBottom}
            />

            <AgentComposer
              isComposerDragActive={isComposerDragActive}
              draftAttachmentPreviews={draftAttachmentPreviews}
              previewAttachmentId={previewAttachmentId}
              setPreviewAttachmentId={setPreviewAttachmentId}
              onRemoveAttachment={removeDraftAttachment}
              composerTextareaRef={composerTextareaRef}
              fileInputRef={fileInputRef}
              draftMessage={draftMessage}
              isMutating={isMutating}
              isRunInFlight={isRunInFlight}
              isSendingMessage={isSendingMessage}
              isInterruptPending={interruptRunMutation.isPending}
              actionError={actionError}
              onSubmit={handleSubmitMessage}
              onDragEnter={handleComposerDragEnter}
              onDragOver={handleComposerDragOver}
              onDragLeave={handleComposerDragLeave}
              onDrop={handleComposerDrop}
              onMessageChange={handleDraftMessageChange}
              onComposerKeyDown={handleComposerKeyDown}
              onComposerPaste={handleComposerPaste}
              onFileSelection={handleDraftFileSelection}
              onStopRun={() => {
                void handleStopRun();
              }}
            />
          </section>

          {isThreadPanelOpen ? (
            <div
              className="agent-resize-handle"
              onMouseDown={handleResizeMouseDown}
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize threads panel"
            />
          ) : null}

          <div
            className="agent-thread-panel-slot"
            style={isThreadPanelOpen ? { width: panelWidth } : undefined}
          >
            <AgentThreadPanel
              threads={threadsQuery.data}
              selectedThreadId={selectedThreadId}
              isLoading={threadsQuery.isLoading}
              errorMessage={threadsQuery.isError ? (threadsQuery.error as Error).message : null}
              onSelectThread={setSelectedThreadId}
              onDeleteThread={(threadId) => {
                void handleDeleteThread(threadId);
              }}
              deletingThreadId={deleteThreadMutation.isPending ? (deleteThreadMutation.variables ?? null) : null}
              isDeleteDisabled={isMutating || isRunInFlight}
              isOpen={isThreadPanelOpen}
            />
          </div>
        </div>

        <AgentRunReviewModal
          open={Boolean(selectedRunForReview)}
          run={selectedRunForReview}
          onOpenChange={(nextOpen) => {
            if (!nextOpen) {
              setReviewRunId(null);
            }
          }}
          onApproveItem={handleApproveItem}
          onRejectItem={handleRejectItem}
          isBusy={isMutating}
        />
      </aside>

      <AgentAttachmentPreviewDialog
        preview={selectedDraftAttachmentPreview}
        onClose={() => {
          setPreviewAttachmentId(null);
        }}
      />
    </>
  );
}

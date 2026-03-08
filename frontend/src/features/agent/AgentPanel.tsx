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
  getAgentToolCall,
  getAgentThread,
  getRuntimeSettings,
  interruptAgentRun,
  listAgentThreads,
  renameAgentThread,
  rejectAgentChangeItem,
  sendAgentMessage,
  streamAgentMessage
} from "../../lib/api";
import { invalidateAgentThreadData, invalidateEntryReadModels } from "../../lib/queryInvalidation";
import { queryKeys } from "../../lib/queryKeys";
import type {
  AgentChangeItem,
  AgentRun,
  AgentRunEvent,
  AgentStreamEvent,
  AgentThread,
  AgentThreadDetail,
  AgentThreadSummary,
  AgentToolCall,
  RuntimeSettings
} from "../../lib/types";
import {
  buildThreadUsageTotals,
  mergeRunToolCalls,
  runsByAssistantMessage,
  runsWithoutAssistantMessageByUserMessage,
  runsWithoutAssistantMessage,
  sortRunsByCreatedAt
} from "./activity";
import { AgentComposer } from "./panel/AgentComposer";
import { AgentAttachmentPreviewDialog } from "./panel/AgentAttachmentPreviewDialog";
import { AgentThreadPanel } from "./panel/AgentThreadPanel";
import { AgentThreadUsageBar } from "./panel/AgentThreadUsageBar";
import { AgentTimeline } from "./panel/AgentTimeline";
import { useStickToBottom } from "./panel/useStickToBottom";
import { useAgentDraftAttachments } from "./panel/useAgentDraftAttachments";
import {
  COMPOSER_TEXTAREA_MAX_HEIGHT_PX,
  type DraftAttachment,
  detectDraftAttachmentKind,
  type PendingAssistantMessage,
  type PendingUserMessage
} from "./panel/types";
import { AgentThreadReviewModal } from "./review/AgentThreadReviewModal";
import { useResizablePanel } from "../../hooks/useResizablePanel";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { useNotifications } from "../../components/ui/notification-center";

interface AgentPanelProps {
  isOpen: boolean;
  onClose?: () => void;
}

const BULK_MODE_HELP_TEXT =
  "Each file starts a fresh thread using only the prompt typed here. Current thread history is not included.";
const DEFAULT_BULK_LAUNCH_CONCURRENCY_LIMIT = 4;

function normalizeThreadTitleValue(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized || null;
}

function extractRenameThreadTitle(toolCall: AgentToolCall): string | null {
  const outputTitle = normalizeThreadTitleValue(toolCall.output_json?.title);
  if (outputTitle) {
    return outputTitle;
  }
  return normalizeThreadTitleValue(toolCall.input_json?.title);
}

function deriveThreadTitleFromFilename(filename: string): string {
  const stem = filename.replace(/\.[^./\\]+$/, "");
  const normalized = stem.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  const nextTitle = normalized || filename.trim() || "Bulk upload";
  return nextTitle.slice(0, 255);
}

function normalizeModelName(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim();
  return normalized || null;
}

function resolveComposerModelName(
  availableModels: string[],
  threadDetail?: AgentThreadDetail,
  runtimeSettings?: RuntimeSettings
): string {
  const latestRunModelName = normalizeModelName(threadDetail?.runs.at(-1)?.model_name);
  const configuredModelName = normalizeModelName(threadDetail?.configured_model_name);
  const runtimeDefaultModelName = normalizeModelName(runtimeSettings?.agent_model);
  const fallbackModelName = normalizeModelName(availableModels[0]);

  for (const candidate of [latestRunModelName, configuredModelName, runtimeDefaultModelName, fallbackModelName]) {
    if (candidate && availableModels.includes(candidate)) {
      return candidate;
    }
  }

  return latestRunModelName ?? configuredModelName ?? runtimeDefaultModelName ?? fallbackModelName ?? "";
}

function buildThreadSummary(thread: AgentThread, overrides: Partial<AgentThreadSummary> = {}): AgentThreadSummary {
  return {
    ...thread,
    last_message_preview: null,
    pending_change_count: 0,
    has_running_run: false,
    ...overrides
  };
}

function summarizeFilenames(fileNames: string[]): string {
  if (fileNames.length <= 3) {
    return fileNames.join(", ");
  }
  return `${fileNames.slice(0, 3).join(", ")}, and ${fileNames.length - 3} more`;
}

async function mapWithConcurrency<T, R>(
  items: readonly T[],
  concurrency: number,
  iteratee: (item: T, index: number) => Promise<R>
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let nextIndex = 0;

  async function worker() {
    while (nextIndex < items.length) {
      const currentIndex = nextIndex;
      nextIndex += 1;
      results[currentIndex] = await iteratee(items[currentIndex], currentIndex);
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, () => worker()));
  return results;
}

export function AgentPanel({ isOpen, onClose }: AgentPanelProps) {
  const queryClient = useQueryClient();
  const { notify } = useNotifications();
  const [selectedThreadId, setSelectedThreadId] = useState<string>("");
  const [draftMessage, setDraftMessage] = useState("");
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [isBulkMode, setIsBulkMode] = useState(false);
  const [isBulkLaunching, setIsBulkLaunching] = useState(false);
  const [isStreamHealthy, setIsStreamHealthy] = useState(false);
  const [activeStreamRunId, setActiveStreamRunId] = useState<string | null>(null);
  const [streamedReasoningTextByRunId, setStreamedReasoningTextByRunId] = useState<Record<string, string>>({});
  const [streamedTextByRunId, setStreamedTextByRunId] = useState<Record<string, string>>({});
  const [optimisticRunEventsByRunId, setOptimisticRunEventsByRunId] = useState<Record<string, AgentRunEvent[]>>({});
  const [optimisticToolCallsByRunId, setOptimisticToolCallsByRunId] = useState<Record<string, AgentToolCall[]>>({});
  const [optimisticThreadTitlesById, setOptimisticThreadTitlesById] = useState<Record<string, string>>({});
  const [optimisticRunningThreadIds, setOptimisticRunningThreadIds] = useState<string[]>([]);
  const [hydratingToolCallIds, setHydratingToolCallIds] = useState<Set<string>>(new Set());
  const [pendingUserMessage, setPendingUserMessage] = useState<PendingUserMessage | null>(null);
  const [pendingAssistantMessage, setPendingAssistantMessage] = useState<PendingAssistantMessage | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isThreadReviewOpen, setIsThreadReviewOpen] = useState(false);
  const { containerRef: timelineScrollRef, isAtBottom, scrollToBottom, snapToBottom } = useStickToBottom<HTMLDivElement>();
  const composerTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [composerModelOverride, setComposerModelOverride] = useState<string | null>(null);
  const sendAbortControllerRef = useRef<AbortController | null>(null);
  const threadRunsRef = useRef<AgentRun[]>([]);
  const optimisticToolCallsRef = useRef<Record<string, AgentToolCall[]>>({});
  const hydratingToolCallIdsRef = useRef<Set<string>>(new Set());
  const [isThreadPanelOpen, setIsThreadPanelOpen] = useState(true);
  const { panelWidth, handleMouseDown: handleResizeMouseDown } = useResizablePanel({
    storageKey: "agent-thread-panel-width",
    defaultWidth: 300,
    minWidth: 200,
    maxWidth: 600,
    edge: "right"
  });
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

  const resetOptimisticRunState = useCallback(() => {
    setActiveStreamRunId(null);
    setStreamedReasoningTextByRunId({});
    setStreamedTextByRunId({});
    setOptimisticRunEventsByRunId({});
    setOptimisticToolCallsByRunId({});
    setHydratingToolCallIds(new Set());
    hydratingToolCallIdsRef.current.clear();
  }, []);

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
  const availableComposerModels = runtimeSettingsQuery.data?.available_agent_models ?? [];
  const resolvedComposerModel = useMemo(
    () => resolveComposerModelName(availableComposerModels, threadQuery.data, runtimeSettingsQuery.data),
    [availableComposerModels, threadQuery.data, runtimeSettingsQuery.data]
  );
  const selectedComposerModel =
    composerModelOverride && availableComposerModels.includes(composerModelOverride) ? composerModelOverride : resolvedComposerModel;
  const bulkLaunchConcurrencyLimit =
    runtimeSettingsQuery.data?.agent_bulk_max_concurrent_threads ?? DEFAULT_BULK_LAUNCH_CONCURRENCY_LIMIT;
  const lastSnappedThreadRef = useRef("");

  useEffect(() => {
    setComposerModelOverride(null);
  }, [selectedThreadId]);

  useEffect(() => {
    if (composerModelOverride && !availableComposerModels.includes(composerModelOverride)) {
      setComposerModelOverride(null);
    }
  }, [availableComposerModels, composerModelOverride]);

  useEffect(() => {
    threadRunsRef.current = threadQuery.data?.runs ?? [];
  }, [threadQuery.data?.runs]);

  useEffect(() => {
    optimisticToolCallsRef.current = optimisticToolCallsByRunId;
  }, [optimisticToolCallsByRunId]);

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
      setIsThreadReviewOpen(false);
      setPendingUserMessage(null);
      setPendingAssistantMessage(null);
      removeOptimisticRunningThreadId(deletedThreadId);
      resetOptimisticRunState();
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

  const upsertThreadSummary = useCallback(
    (thread: AgentThreadSummary) => {
      queryClient.setQueryData(queryKeys.agent.threads, (current: AgentThreadSummary[] | undefined) => {
        const nextThreads = [thread, ...(current ?? []).filter((item) => item.id !== thread.id)];
        return nextThreads.sort((left, right) => right.updated_at.localeCompare(left.updated_at));
      });
    },
    [queryClient]
  );

  const addOptimisticRunningThreadId = useCallback((threadId: string) => {
    setOptimisticRunningThreadIds((current) => (current.includes(threadId) ? current : [...current, threadId]));
  }, []);

  const removeOptimisticRunningThreadId = useCallback((threadId: string) => {
    setOptimisticRunningThreadIds((current) => current.filter((item) => item !== threadId));
  }, []);

  const renameThreadMutation = useMutation({
    mutationFn: renameAgentThread,
    onSuccess: (thread) => {
      applyThreadTitleToCaches(thread.id, thread.title, thread.updated_at);
      setOptimisticThreadTitlesById((current) => {
        const next = { ...current };
        delete next[thread.id];
        return next;
      });
      setActionError(null);
    }
  });

  const interruptRunMutation = useMutation({
    mutationFn: interruptAgentRun,
    onSuccess: () => {
      invalidateAgentThreadData(queryClient, selectedThreadId || undefined);
      setIsStreamHealthy(false);
      resetOptimisticRunState();
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
    renameThreadMutation.isPending ||
    interruptRunMutation.isPending ||
    approveMutation.isPending ||
    rejectMutation.isPending;

  const runsByAssistantMessageId = useMemo(() => runsByAssistantMessage(threadQuery.data), [threadQuery.data]);
  const pendingAssistantRuns = useMemo(() => runsWithoutAssistantMessage(threadQuery.data), [threadQuery.data]);
  const pendingAssistantRunsByUserMessageId = useMemo(
    () => runsWithoutAssistantMessageByUserMessage(threadQuery.data),
    [threadQuery.data]
  );
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
    if (activeStreamRunId) {
      return (threadQuery.data?.runs ?? []).find((run) => run.id === activeStreamRunId) ?? null;
    }
    const runningRun = [...pendingAssistantRuns].reverse().find((run) => run.status === "running");
    return runningRun ?? null;
  }, [activeStreamRunId, pendingAssistantMessage, pendingAssistantRuns, selectedThreadId, threadQuery.data?.runs]);
  const activeStreamText = useMemo(() => {
    if (!activeStreamRunId) {
      return "";
    }
    return streamedTextByRunId[activeStreamRunId] ?? "";
  }, [activeStreamRunId, streamedTextByRunId]);
  const activeStreamReasoningText = useMemo(() => {
    if (!activeStreamRunId) {
      return "";
    }
    return streamedReasoningTextByRunId[activeStreamRunId] ?? "";
  }, [activeStreamRunId, streamedReasoningTextByRunId]);
  const activeOptimisticEvents = useMemo(() => {
    if (!activeStreamRunId) {
      return [];
    }
    return optimisticRunEventsByRunId[activeStreamRunId] ?? [];
  }, [activeStreamRunId, optimisticRunEventsByRunId]);
  const activeOptimisticToolCalls = useMemo(() => {
    if (!activeStreamRunId) {
      return [];
    }
    return optimisticToolCallsByRunId[activeStreamRunId] ?? [];
  }, [activeStreamRunId, optimisticToolCallsByRunId]);
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
    resetOptimisticRunState();
    setIsStreamHealthy(false);
  }, [pendingAssistantMessage, resetOptimisticRunState, selectedThreadId, threadQuery.data?.messages]);

  const persistedActiveModelName = useMemo(() => {
    const runs = threadQuery.data?.runs ?? [];
    const latest = runs[runs.length - 1];
    const runModelName = latest?.model_name?.trim();
    if (runModelName) {
      return runModelName;
    }
    const configuredModelName = threadQuery.data?.configured_model_name?.trim();
    return configuredModelName || "unknown model";
  }, [threadQuery.data?.runs, threadQuery.data?.configured_model_name]);
  const activeModelName =
    composerModelOverride && availableComposerModels.includes(composerModelOverride)
      ? composerModelOverride
      : persistedActiveModelName;

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
    setIsThreadReviewOpen(false);
    setPendingAssistantMessage(null);
    resetOptimisticRunState();
    setIsStreamHealthy(false);
  }, [resetOptimisticRunState, selectedThreadId]);

  useEffect(() => {
    if (!pendingAssistantMessage) {
      return;
    }
    if (pendingAssistantMessage.threadId !== selectedThreadId) {
      return;
    }
    if (!isRunInFlight && !pendingUserMessage) {
      setPendingAssistantMessage(null);
      resetOptimisticRunState();
      setIsStreamHealthy(false);
    }
  }, [isRunInFlight, pendingAssistantMessage, pendingUserMessage, resetOptimisticRunState, selectedThreadId]);

  function handleComposerModelChange(event: ChangeEvent<HTMLSelectElement>) {
    setComposerModelOverride(event.target.value);
  }

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

  async function handleRenameThread(threadId: string, title: string) {
    setActionError(null);
    try {
      await renameThreadMutation.mutateAsync({ threadId, title });
    } catch (error) {
      setActionError((error as Error).message);
      throw error;
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

  const hydrateToolCallDetails = useCallback(async (threadId: string, runId: string, toolCallId: string, force = false) => {
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
          existing.every((toolCall, index) => {
            const nextToolCall = nextToolCalls[index];
            return (
              nextToolCall &&
              toolCall.id === nextToolCall.id &&
              toolCall.status === nextToolCall.status &&
              toolCall.has_full_payload === nextToolCall.has_full_payload
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
  }, [applyThreadTitleToCaches]);

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
      setOptimisticThreadTitlesById((current) => {
        const next = { ...current };
        delete next[activeThreadId];
        return next;
      });
      invalidateAgentThreadData(queryClient, activeThreadId);
      setPendingUserMessage((current) => {
        if (!current || current.threadId !== activeThreadId) {
          return current;
        }
        return null;
      });
      setPendingAssistantMessage((current) => {
        if (!current || current.threadId !== activeThreadId) {
          return current;
        }
        return null;
      });
      removeOptimisticRunningThreadId(activeThreadId);
      resetOptimisticRunState();
    } catch (error) {
      sendAbortControllerRef.current = null;
      setIsStreamHealthy(false);
      if ((error as Error).name === "AbortError") {
        setPendingUserMessage((current) => {
          return current ? null : current;
        });
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
    if (isMutating || isBulkLaunching || (!isBulkMode && isRunInFlight)) {
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
      invalidateAgentThreadData(queryClient, selectedThreadId || undefined);
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

  function handleBulkModeChange(checked: boolean) {
    setIsBulkMode(checked);
    setActionError(null);
  }

  if (!isOpen) {
    return null;
  }

  return (
    <>
      <aside className="agent-panel agent-panel-page" aria-label="Agent panel">
        <header className="agent-panel-header">
          <div className="agent-panel-header-top">
            <h2>{`Agent (${activeModelName})`}</h2>
            <div className="agent-panel-header-actions">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setIsThreadReviewOpen(true)}
                disabled={!selectedThreadId || reviewProposalCount === 0 || isMutating || isBulkLaunching}
                className={`agent-panel-review-button${pendingReviewCount > 0 ? " is-pending" : ""}`}
              >
                <span>Review</span>
                {pendingReviewCount > 0 ? (
                  <Badge variant="outline" className="agent-panel-review-badge">
                    {pendingReviewCount}
                  </Badge>
                ) : null}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  void handleCreateThread();
                }}
                disabled={isMutating || isBulkLaunching}
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
          </div>
          <AgentThreadUsageBar selectedThreadId={selectedThreadId} totals={threadUsageTotals} />
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
              pendingAssistantRunsByUserMessageId={pendingAssistantRunsByUserMessageId}
              pendingUserMessage={pendingUserMessage}
              pendingAssistantMessage={pendingAssistantMessage}
              shouldShowOptimisticAssistantBubble={shouldShowOptimisticAssistantBubble}
              pendingRunAttachedToOptimisticMessage={pendingRunAttachedToOptimisticMessage}
              isMutating={isMutating}
              activeStreamReasoningText={activeStreamReasoningText}
              activeStreamText={activeStreamText}
              optimisticRunEventsByRunId={optimisticRunEventsByRunId}
              optimisticToolCallsByRunId={optimisticToolCallsByRunId}
              activeOptimisticEvents={activeOptimisticEvents}
              activeOptimisticToolCalls={activeOptimisticToolCalls}
              onHydrateToolCall={handleHydrateToolCall}
              hydratingToolCallIds={hydratingToolCallIds}
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
              availableModels={availableComposerModels}
              selectedModel={selectedComposerModel}
              isModelPickerDisabled={isMutating || isBulkLaunching}
              isMutating={isMutating}
              isRunInFlight={isRunInFlight}
              isSendingMessage={isSendingMessage}
              isBulkMode={isBulkMode}
              isBulkLaunching={isBulkLaunching}
              isInterruptPending={interruptRunMutation.isPending}
              bulkModeHelpText={BULK_MODE_HELP_TEXT}
              actionError={actionError}
              onBulkModeChange={handleBulkModeChange}
              onSubmit={handleSubmitMessage}
              onDragEnter={handleComposerDragEnter}
              onDragOver={handleComposerDragOver}
              onDragLeave={handleComposerDragLeave}
              onDrop={handleComposerDrop}
              onMessageChange={handleDraftMessageChange}
              onModelChange={handleComposerModelChange}
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
              className="panel-resize-handle agent-resize-handle"
              onMouseDown={handleResizeMouseDown}
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize threads panel"
            />
          ) : null}

          <div
            className={isThreadPanelOpen ? "agent-thread-panel-slot" : "agent-thread-panel-slot agent-thread-panel-slot-collapsed"}
            style={isThreadPanelOpen ? { width: panelWidth } : undefined}
          >
            <AgentThreadPanel
              threads={displayedThreads}
              selectedThreadId={selectedThreadId}
              isLoading={threadsQuery.isLoading}
              errorMessage={threadsQuery.isError ? (threadsQuery.error as Error).message : null}
              onSelectThread={setSelectedThreadId}
              onRenameThread={handleRenameThread}
              onDeleteThread={(threadId) => {
                void handleDeleteThread(threadId);
              }}
              renamingThreadId={renameThreadMutation.isPending ? (renameThreadMutation.variables?.threadId ?? null) : null}
              deletingThreadId={deleteThreadMutation.isPending ? (deleteThreadMutation.variables ?? null) : null}
              isDeleteDisabled={isMutating || isRunInFlight || isBulkLaunching}
              isRenameDisabled={isMutating || isRunInFlight || isBulkLaunching}
              isOpen={isThreadPanelOpen}
              optimisticRunningThreadIds={optimisticRunningThreadIds}
            />
          </div>
        </div>

        <AgentThreadReviewModal
          open={isThreadReviewOpen}
          runs={threadQuery.data?.runs ?? []}
          onOpenChange={setIsThreadReviewOpen}
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

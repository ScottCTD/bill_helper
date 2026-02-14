import {
  type ChangeEvent,
  type ClipboardEvent,
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { ChevronRight, Paperclip, SendHorizontal, Square, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  approveAgentChangeItem,
  createAgentThread,
  getAgentThread,
  interruptAgentRun,
  listAgentThreads,
  rejectAgentChangeItem,
  streamAgentMessage,
  withApiBase
} from "../../lib/api";
import { invalidateAgentThreadData, invalidateEntryReadModels } from "../../lib/queryInvalidation";
import { queryKeys } from "../../lib/queryKeys";
import type { AgentChangeItem, AgentRun, AgentStreamEvent, AgentThreadDetail, AgentThreadSummary } from "../../lib/types";
import { cn } from "../../lib/utils";
import { AgentRunReviewModal } from "./review/AgentRunReviewModal";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { MarkdownRenderer } from "../ui/MarkdownRenderer";
import { Textarea } from "../ui/textarea";

interface AgentPanelProps {
  isOpen: boolean;
  onClose?: () => void;
}

interface DraftAttachment {
  id: string;
  file: File;
}

interface DraftAttachmentPreview {
  id: string;
  file: File;
  url: string;
}

interface PendingUserAttachmentPreview {
  id: string;
  name: string;
  url: string;
}

interface PendingUserMessage {
  id: string;
  threadId: string;
  content: string;
  createdAt: string;
  baselineLastUserMessageId: string | null;
  attachments: PendingUserAttachmentPreview[];
}

interface PendingAssistantMessage {
  id: string;
  threadId: string;
  createdAt: string;
  content: string;
  runId: string | null;
  baselineLastAssistantMessageId: string | null;
}

const IMAGE_FILENAME_PATTERN = /\.(avif|bmp|gif|heic|heif|jpe?g|png|svg|tiff?|webp)$/i;
const COMPOSER_TEXTAREA_MAX_HEIGHT_PX = 220;

function prettyDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function compactThreadName(thread: AgentThreadSummary): string {
  const source = (thread.title || "").trim();
  if (!source) {
    return "Untitled thread";
  }
  const normalized = source.replace(/\s+/g, " ");
  return normalized.slice(0, 20);
}

function sortRunsByCreatedAt(runs: AgentRun[]): AgentRun[] {
  return [...runs].sort((left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime());
}

function runsByAssistantMessage(detail: AgentThreadDetail | undefined): Map<string, AgentRun[]> {
  const map = new Map<string, AgentRun[]>();
  sortRunsByCreatedAt(detail?.runs ?? []).forEach((run) => {
    if (!run.assistant_message_id) {
      return;
    }
    const runs = map.get(run.assistant_message_id);
    if (runs) {
      runs.push(run);
      return;
    }
    map.set(run.assistant_message_id, [run]);
  });
  return map;
}

function runsWithoutAssistantMessage(detail: AgentThreadDetail | undefined): AgentRun[] {
  return sortRunsByCreatedAt((detail?.runs ?? []).filter((run) => !run.assistant_message_id));
}

function totalRunMetric(
  runs: AgentRun[],
  field: "input_tokens" | "output_tokens" | "cache_read_tokens" | "cache_write_tokens" | "total_cost_usd"
): number | null {
  let total = 0;
  let hasValue = false;
  runs.forEach((run) => {
    const value = run[field];
    if (typeof value === "number") {
      total += value;
      hasValue = true;
    }
  });
  return hasValue ? total : null;
}

function summarizeRunChangeTypes(changeItems: AgentChangeItem[]): {
  entryCount: number;
  tagCount: number;
  entityCount: number;
} {
  let entryCount = 0;
  let tagCount = 0;
  let entityCount = 0;

  changeItems.forEach((item) => {
    if (item.change_type.endsWith("_entry")) {
      entryCount += 1;
      return;
    }
    if (item.change_type.endsWith("_tag")) {
      tagCount += 1;
      return;
    }
    if (item.change_type.endsWith("_entity")) {
      entityCount += 1;
    }
  });

  return {
    entryCount,
    tagCount,
    entityCount
  };
}

function formatUsageTokens(value: number | null): string {
  return value === null ? "-" : value.toLocaleString();
}

function formatUsdCost(value: number | null): string {
  if (value === null) {
    return "-";
  }
  const abs = Math.abs(value);
  const fractionDigits = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits
  }).format(value);
}

interface AgentRunBlockProps {
  run: AgentRun;
  isMutating: boolean;
  onReviewRun: (runId: string) => void;
  mode?: "activity" | "summary" | "all";
}

function AgentRunBlock({ run, isMutating, onReviewRun, mode = "all" }: AgentRunBlockProps) {
  const showActivity = mode !== "summary";
  const showSummary = mode !== "activity";
  const hasSummaryChanges = showSummary && run.change_items.length > 0;
  const hasActivityContent = Boolean(run.error_text) || run.tool_calls.length > 0;
  const pendingCount = run.change_items.filter((item) => item.status === "PENDING_REVIEW").length;
  const failedCount = run.change_items.filter((item) => item.status === "APPLY_FAILED").length;
  const typeSummary = summarizeRunChangeTypes(run.change_items);
  const [isToolListExpanded, setIsToolListExpanded] = useState(run.status === "running");
  const previousToolCallCountRef = useRef(run.tool_calls.length);

  useEffect(() => {
    const previousCount = previousToolCallCountRef.current;
    previousToolCallCountRef.current = run.tool_calls.length;
    if (run.status !== "running") {
      setIsToolListExpanded(false);
      return;
    }
    if (run.tool_calls.length > previousCount) {
      setIsToolListExpanded(true);
    }
  }, [run.status, run.tool_calls.length]);

  if (!hasActivityContent && !hasSummaryChanges) {
    return null;
  }

  return (
    <div className={cn("agent-run-block", showSummary && "agent-run-block-summary")}>
      {showActivity ? (
        <>
          {run.error_text ? <p className="error">{run.error_text}</p> : null}

          {run.tool_calls.length > 0 ? (
            <div className="agent-run-tools">
              <details
                className="agent-tool-call-group"
                open={isToolListExpanded}
                onToggle={(event) => setIsToolListExpanded(event.currentTarget.open)}
              >
                <summary>
                  <ChevronRight className="agent-tool-call-chevron" />
                  <span className="agent-tool-call-group-label">
                    {run.tool_calls.length} tool call{run.tool_calls.length === 1 ? "" : "s"}
                  </span>
                </summary>
                <ul className="agent-tool-call-list">
                  {run.tool_calls.map((toolCall) => (
                    <li key={toolCall.id}>
                      <details className="agent-tool-call">
                        <summary>
                          <ChevronRight className="agent-tool-call-chevron" />
                          <span className="agent-tool-call-name">{toolCall.tool_name}</span>
                          <span className="agent-tool-call-status">{toolCall.status}</span>
                          <span className="agent-tool-call-time muted">{prettyDateTime(toolCall.created_at)}</span>
                        </summary>
                        <div className="agent-tool-call-details">
                          <p className="agent-tool-call-details-label">Input</p>
                          <pre>{JSON.stringify(toolCall.input_json, null, 2)}</pre>
                          <p className="agent-tool-call-details-label">Output</p>
                          <pre>{JSON.stringify(toolCall.output_json, null, 2)}</pre>
                        </div>
                      </details>
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          ) : null}
        </>
      ) : null}

      {hasSummaryChanges ? (
        <div className="agent-run-changes-summary">
          <h4>{pendingCount > 0 ? `${pendingCount} proposed changes pending review` : "No pending changes in this run"}</h4>
          <Button type="button" size="sm" onClick={() => onReviewRun(run.id)} disabled={isMutating}>
            {pendingCount > 0 ? "Click to review proposed changes" : "View reviewed changes"}
          </Button>
          <div className="agent-run-change-chips">
            <span className="agent-run-change-chip">Entry x{typeSummary.entryCount}</span>
            <span className="agent-run-change-chip">Tag x{typeSummary.tagCount}</span>
            <span className="agent-run-change-chip">Entity x{typeSummary.entityCount}</span>
          </div>
          {failedCount > 0 ? (
            <p className="error">
              {failedCount} apply failure{failedCount === 1 ? "" : "s"} detected. Open review for details.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function AgentPanel({ isOpen, onClose }: AgentPanelProps) {
  const queryClient = useQueryClient();
  const [selectedThreadId, setSelectedThreadId] = useState<string>("");
  const [draftMessage, setDraftMessage] = useState("");
  const [draftFiles, setDraftFiles] = useState<DraftAttachment[]>([]);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [isSendPolling, setIsSendPolling] = useState(false);
  const [pendingUserMessage, setPendingUserMessage] = useState<PendingUserMessage | null>(null);
  const [pendingAssistantMessage, setPendingAssistantMessage] = useState<PendingAssistantMessage | null>(null);
  const [previewAttachmentId, setPreviewAttachmentId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [reviewRunId, setReviewRunId] = useState<string | null>(null);
  const [isComposerDragActive, setIsComposerDragActive] = useState(false);
  const draftFileIdCounterRef = useRef(0);
  const composerDragDepthRef = useRef(0);
  const timelineScrollRef = useRef<HTMLDivElement | null>(null);
  const composerTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const sendAbortControllerRef = useRef<AbortController | null>(null);

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
  useEffect(() => {
    const timeline = timelineScrollRef.current;
    if (!timeline) {
      return;
    }
    timeline.scrollTop = timeline.scrollHeight;
  }, [selectedThreadId, threadMessages]);

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
    const runs = threadQuery.data?.runs ?? [];
    return {
      input: totalRunMetric(runs, "input_tokens"),
      output: totalRunMetric(runs, "output_tokens"),
      cacheRead: totalRunMetric(runs, "cache_read_tokens"),
      cacheWrite: totalRunMetric(runs, "cache_write_tokens"),
      totalCost: totalRunMetric(runs, "total_cost_usd")
    };
  }, [threadQuery.data?.runs]);

  const draftAttachmentPreviews = useMemo<DraftAttachmentPreview[]>(
    () => draftFiles.map((item) => ({ id: item.id, file: item.file, url: URL.createObjectURL(item.file) })),
    [draftFiles]
  );

  useEffect(() => {
    return () => {
      draftAttachmentPreviews.forEach((preview) => {
        URL.revokeObjectURL(preview.url);
      });
    };
  }, [draftAttachmentPreviews]);

  const selectedDraftAttachmentPreview = useMemo(
    () => draftAttachmentPreviews.find((preview) => preview.id === previewAttachmentId) ?? null,
    [draftAttachmentPreviews, previewAttachmentId]
  );

  useEffect(() => {
    if (!previewAttachmentId) {
      return;
    }
    if (selectedDraftAttachmentPreview) {
      return;
    }
    setPreviewAttachmentId(null);
  }, [previewAttachmentId, selectedDraftAttachmentPreview]);

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

  function nextDraftAttachmentId(): string {
    draftFileIdCounterRef.current += 1;
    return `draft-attachment-${draftFileIdCounterRef.current}`;
  }

  function handleDraftFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (files.length === 0) {
      return;
    }
    appendDraftAttachments(files);
    event.target.value = "";
  }

  function isImageFile(file: File): boolean {
    const mimeType = file.type.toLowerCase();
    if (mimeType.startsWith("image/")) {
      return true;
    }
    return IMAGE_FILENAME_PATTERN.test(file.name.toLowerCase());
  }

  function appendDraftAttachments(files: File[]): void {
    if (files.length === 0) {
      return;
    }
    const imageFiles = files.filter(isImageFile);
    const rejectedCount = files.length - imageFiles.length;
    if (rejectedCount > 0) {
      setActionError(
        rejectedCount === 1
          ? "Only image files are supported in agent attachments."
          : `${rejectedCount} files were skipped. Only image files are supported in agent attachments.`
      );
    } else {
      setActionError(null);
    }
    if (imageFiles.length === 0) {
      return;
    }
    setDraftFiles((current) => [
      ...current,
      ...imageFiles.map((file) => ({
        id: nextDraftAttachmentId(),
        file
      }))
    ]);
  }

  function extractClipboardFiles(event: ClipboardEvent<HTMLTextAreaElement>): File[] {
    const itemFiles = Array.from(event.clipboardData.items ?? [])
      .filter((item) => item.kind === "file")
      .map((item) => item.getAsFile())
      .filter((file): file is File => file !== null);
    if (itemFiles.length > 0) {
      return itemFiles;
    }
    return Array.from(event.clipboardData.files ?? []);
  }

  function handleComposerPaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const files = extractClipboardFiles(event);
    if (files.length === 0) {
      return;
    }
    event.preventDefault();
    appendDraftAttachments(files);
  }

  function dataTransferHasFiles(dataTransfer: DataTransfer | null): boolean {
    return !!dataTransfer && Array.from(dataTransfer.types).includes("Files");
  }

  function handleComposerDragEnter(event: DragEvent<HTMLFormElement>) {
    if (!dataTransferHasFiles(event.dataTransfer)) {
      return;
    }
    event.preventDefault();
    composerDragDepthRef.current += 1;
    setIsComposerDragActive(true);
  }

  function handleComposerDragOver(event: DragEvent<HTMLFormElement>) {
    if (!dataTransferHasFiles(event.dataTransfer)) {
      return;
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    if (!isComposerDragActive) {
      setIsComposerDragActive(true);
    }
  }

  function handleComposerDragLeave(event: DragEvent<HTMLFormElement>) {
    if (!dataTransferHasFiles(event.dataTransfer)) {
      return;
    }
    event.preventDefault();
    composerDragDepthRef.current = Math.max(composerDragDepthRef.current - 1, 0);
    if (composerDragDepthRef.current === 0) {
      setIsComposerDragActive(false);
    }
  }

  function handleComposerDrop(event: DragEvent<HTMLFormElement>) {
    if (!dataTransferHasFiles(event.dataTransfer)) {
      return;
    }
    event.preventDefault();
    composerDragDepthRef.current = 0;
    setIsComposerDragActive(false);
    appendDraftAttachments(Array.from(event.dataTransfer.files ?? []));
  }

  function removeDraftAttachment(attachmentId: string) {
    setDraftFiles((current) => current.filter((item) => item.id !== attachmentId));
    if (previewAttachmentId === attachmentId) {
      setPreviewAttachmentId(null);
    }
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

  async function ensureThreadId(): Promise<string> {
    if (selectedThreadId) {
      return selectedThreadId;
    }
    const created = await createThreadMutation.mutateAsync({});
    setSelectedThreadId(created.id);
    return created.id;
  }

  function handleAgentStreamEvent(threadId: string, event: AgentStreamEvent) {
    if (event.type === "run_started") {
      setPendingAssistantMessage((current) => {
        if (!current || current.threadId !== threadId) {
          return current;
        }
        return { ...current, runId: event.run_id };
      });
      return;
    }
    if (event.type === "text_delta") {
      setPendingAssistantMessage((current) => {
        if (!current || current.threadId !== threadId) {
          return current;
        }
        return {
          ...current,
          runId: current.runId || event.run_id,
          content: `${current.content}${event.delta}`
        };
      });
      return;
    }
    if (event.type === "run_failed" && event.error_text) {
      setActionError(event.error_text);
    }
  }

  async function handleSubmitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionError(null);
    const content = draftMessage.trim();
    if (!content && draftFiles.length === 0) {
      setActionError("Enter a message or attach at least one image.");
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
          url: URL.createObjectURL(item.file)
        }))
      };
      setPendingUserMessage(optimisticMessage);
      setPendingAssistantMessage({
        id: `pending-assistant-${Date.now()}`,
        threadId,
        createdAt: new Date().toISOString(),
        content: "",
        runId: null,
        baselineLastAssistantMessageId
      });
      setDraftMessage("");
      setDraftFiles([]);
      setPreviewAttachmentId(null);

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
          <div>
            <h2>{`Agent (${activeModelName})`}</h2>
          </div>
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
          </div>
        </header>

        <div className="agent-panel-body agent-panel-body-page">
          <section className="agent-thread-list agent-thread-list-page">
            <h3>Threads</h3>
            {threadsQuery.isLoading ? <p>Loading threads...</p> : null}
            {threadsQuery.isError ? <p className="error">{(threadsQuery.error as Error).message}</p> : null}
            <div className="agent-thread-list-scroll">
              {(threadsQuery.data ?? []).map((thread) => (
                <Button
                  key={thread.id}
                  type="button"
                  variant="ghost"
                  className={thread.id === selectedThreadId ? "agent-thread-button selected" : "agent-thread-button"}
                  onClick={() => setSelectedThreadId(thread.id)}
                  title={thread.title || "Untitled thread"}
                >
                  <span className="agent-thread-label">{compactThreadName(thread)}</span>
                </Button>
              ))}
            </div>
          </section>

          <section className="agent-thread-timeline agent-thread-main">
            <h3>Timeline</h3>
            {!selectedThreadId ? <p className="muted">Create or select a thread to begin.</p> : null}
            {threadQuery.isLoading ? <p>Loading timeline...</p> : null}
            {threadQuery.isError ? <p className="error">{(threadQuery.error as Error).message}</p> : null}

            {selectedThreadId ? (
              <div className="agent-timeline-scroll" ref={timelineScrollRef}>
                {(threadQuery.data?.messages ?? []).map((message) => {
                  const isAssistant = message.role === "assistant";
                  const isUser = message.role === "user";
                  const shouldRenderMarkdown = !isUser;
                  const renderedContent = message.content_markdown;
                  const messageRuns = isAssistant ? runsByAssistantMessageId.get(message.id) ?? [] : [];

                  return (
                    <article
                      key={message.id}
                      className={cn("agent-message", isAssistant && "agent-message-assistant", isUser && "agent-message-user")}
                    >
                      <header>
                        <strong>{isUser ? "You" : isAssistant ? "Assistant" : message.role}</strong>
                        <span className="muted">{prettyDateTime(message.created_at)}</span>
                      </header>

                      {isAssistant
                        ? messageRuns.map((run) => (
                            <AgentRunBlock
                              key={`${run.id}-activity`}
                              run={run}
                              isMutating={isMutating}
                              onReviewRun={setReviewRunId}
                              mode="activity"
                            />
                          ))
                        : null}

                      {renderedContent.trim() ? (
                        shouldRenderMarkdown ? (
                          <MarkdownRenderer markdown={renderedContent} />
                        ) : (
                          <p className="agent-message-text">{renderedContent}</p>
                        )
                      ) : (
                        <p className="muted">(no text)</p>
                      )}

                      {message.attachments.length > 0 ? (
                        <div className="agent-message-images">
                          {message.attachments.map((attachment) => (
                            <img
                              key={attachment.id}
                              src={withApiBase(attachment.attachment_url)}
                              alt="User upload"
                              loading="lazy"
                            />
                          ))}
                        </div>
                      ) : null}

                      {isAssistant
                        ? messageRuns.map((run) => (
                            <AgentRunBlock
                              key={`${run.id}-summary`}
                              run={run}
                              isMutating={isMutating}
                              onReviewRun={setReviewRunId}
                              mode="summary"
                            />
                          ))
                        : null}
                    </article>
                  );
                })}

                {pendingUserMessage && pendingUserMessage.threadId === selectedThreadId ? (
                  <article className="agent-message agent-message-user" key={pendingUserMessage.id}>
                    <header>
                      <strong>You</strong>
                      <span className="muted">{prettyDateTime(pendingUserMessage.createdAt)}</span>
                    </header>
                    {pendingUserMessage.content ? (
                      <p className="agent-message-text">{pendingUserMessage.content}</p>
                    ) : (
                      <p className="muted">(image-only message)</p>
                    )}
                    {pendingUserMessage.attachments.length > 0 ? (
                      <div className="agent-message-images">
                        {pendingUserMessage.attachments.map((attachment) => (
                          <img key={attachment.id} src={attachment.url} alt={attachment.name} loading="lazy" />
                        ))}
                      </div>
                    ) : null}
                  </article>
                ) : null}

                {shouldShowOptimisticAssistantBubble && pendingAssistantMessage ? (
                  <article className="agent-message agent-message-assistant agent-message-streaming" key={pendingAssistantMessage.id}>
                    <header>
                      <strong>Assistant</strong>
                      <span className="muted">{prettyDateTime(pendingAssistantMessage.createdAt)}</span>
                    </header>
                    {pendingRunAttachedToOptimisticMessage ? (
                      <AgentRunBlock
                        run={pendingRunAttachedToOptimisticMessage}
                        isMutating={isMutating}
                        onReviewRun={setReviewRunId}
                        mode="activity"
                      />
                    ) : null}
                    {pendingAssistantMessage.content.trim() ? (
                      <p className="agent-message-text agent-message-streaming-text">
                        {pendingAssistantMessage.content}
                        <span className="agent-message-caret">{"\u258d"}</span>
                      </p>
                    ) : (
                      <p className="agent-message-text">
                        <span className="agent-message-caret">{"\u258d"}</span>
                      </p>
                    )}
                  </article>
                ) : null}

                {pendingAssistantRuns.map((run) => {
                  const hasVisibleContent = Boolean(run.error_text) || run.tool_calls.length > 0 || run.change_items.length > 0;
                  const attachedToOptimisticMessage =
                    pendingRunAttachedToOptimisticMessage && pendingRunAttachedToOptimisticMessage.id === run.id;
                  if (attachedToOptimisticMessage) {
                    return null;
                  }
                  if (!hasVisibleContent) {
                    return null;
                  }
                  return (
                    <article key={`pending-run-${run.id}`} className="agent-message agent-message-assistant agent-message-working">
                      <header>
                        <strong>Assistant</strong>
                        <span className="muted">{prettyDateTime(run.created_at)}</span>
                      </header>
                      <AgentRunBlock run={run} isMutating={isMutating} onReviewRun={setReviewRunId} />
                    </article>
                  );
                })}
              </div>
            ) : null}

            {selectedThreadId ? (
              <div className="agent-thread-usage" aria-label="Thread usage and cost">
                <span>Input: {formatUsageTokens(threadUsageTotals.input)}</span>
                <span>Output: {formatUsageTokens(threadUsageTotals.output)}</span>
                <span>Cache read: {formatUsageTokens(threadUsageTotals.cacheRead)}</span>
                <span>Cache write: {formatUsageTokens(threadUsageTotals.cacheWrite)}</span>
                <span className="agent-thread-usage-total">Total cost: {formatUsdCost(threadUsageTotals.totalCost)}</span>
              </div>
            ) : null}

            <form
              className={cn("agent-composer", isComposerDragActive && "agent-composer-drop-active")}
              onSubmit={handleSubmitMessage}
              onDragEnter={handleComposerDragEnter}
              onDragOver={handleComposerDragOver}
              onDragLeave={handleComposerDragLeave}
              onDrop={handleComposerDrop}
            >
              {isComposerDragActive ? <p className="muted">Drop files to attach</p> : null}
              {draftAttachmentPreviews.length > 0 ? (
                <div className="agent-draft-attachments" aria-label="Pending attachments">
                  {draftAttachmentPreviews.map((preview) => (
                    <div key={preview.id} className="agent-draft-attachment-chip">
                      <button
                        type="button"
                        className="agent-draft-attachment-preview"
                        onClick={() => setPreviewAttachmentId(preview.id)}
                        title={preview.file.name}
                      >
                        <img src={preview.url} alt={preview.file.name} loading="lazy" />
                      </button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="agent-draft-attachment-remove !size-4"
                        onClick={() => removeDraftAttachment(preview.id)}
                        aria-label={`Remove ${preview.file.name}`}
                      >
                        <X className="h-2 w-2" />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="agent-composer-box">
                <Textarea
                  ref={composerTextareaRef}
                  className="agent-composer-textarea border-none shadow-none focus-visible:ring-0"
                  placeholder="Ask a question or ask the agent to propose entries/tags/entities..."
                  value={draftMessage}
                  onChange={handleDraftMessageChange}
                  onKeyDown={handleComposerKeyDown}
                  onPaste={handleComposerPaste}
                  rows={1}
                />

                <div className="agent-composer-toolbar">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={handleDraftFileSelection}
                    className="sr-only"
                    tabIndex={-1}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="agent-composer-attach"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Paperclip className="h-4 w-4" />
                    Add Attachments
                  </Button>

                  {isRunInFlight ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      disabled={interruptRunMutation.isPending}
                      className="agent-composer-send"
                      onClick={handleStopRun}
                    >
                      {interruptRunMutation.isPending ? "Stopping..." : "Stop"}
                      <Square className="h-3.5 w-3.5" />
                    </Button>
                  ) : (
                    <Button type="submit" size="sm" disabled={isMutating} className="agent-composer-send">
                      {isSendingMessage ? "Sending..." : "Send"}
                      <SendHorizontal className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
              {actionError ? <p className="error">{actionError}</p> : null}
            </form>
          </section>
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

      <Dialog
        open={Boolean(selectedDraftAttachmentPreview)}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) {
            setPreviewAttachmentId(null);
          }
        }}
      >
        <DialogContent className="agent-attachment-preview-dialog">
          <DialogHeader>
            <DialogTitle>{selectedDraftAttachmentPreview?.file.name ?? "Attachment preview"}</DialogTitle>
          </DialogHeader>
          {selectedDraftAttachmentPreview ? (
            <img
              src={selectedDraftAttachmentPreview.url}
              alt={selectedDraftAttachmentPreview.file.name}
              className="agent-attachment-preview-image"
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

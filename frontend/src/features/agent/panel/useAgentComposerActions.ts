import { type Dispatch, type FormEvent, type SetStateAction, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useNotifications } from "../../../components/ui/notification-center";
import { createAgentThread, deleteAgentThread, getAgentThread, sendAgentMessage, streamAgentMessage } from "../../../lib/api";
import { invalidateAgentThreadData } from "../../../lib/queryInvalidation";
import { queryKeys } from "../../../lib/queryKeys";
import type { AgentStreamEvent, AgentThread, AgentThreadDetail, AgentThreadSummary } from "../../../lib/types";
import { sortRunsByCreatedAt } from "../activity";
import {
  buildThreadSummary,
  deriveThreadTitleFromFilename,
  mapWithConcurrency,
  summarizeFilenames
} from "./helpers";
import { detectDraftAttachmentKind, type DraftAttachment, type PendingAssistantMessage, type PendingUserMessage } from "./types";

interface UseAgentComposerActionsArgs {
  activeRunId: string | null;
  activeStreamRunId: string | null;
  addOptimisticRunningThreadId: (threadId: string) => void;
  bulkLaunchConcurrencyLimit: number;
  clearOptimisticThreadTitle: (threadId: string) => void;
  draftFiles: DraftAttachment[];
  draftMessage: string;
  ensureThreadId: () => Promise<string>;
  handleAgentStreamEvent: (threadId: string, event: AgentStreamEvent) => void;
  interruptRun: (runId: string) => Promise<void>;
  isBulkMode: boolean;
  removeOptimisticRunningThreadId: (threadId: string) => void;
  resetOptimisticRunState: () => void;
  selectedComposerModel: string;
  selectedThreadId: string;
  setActionError: (message: string | null) => void;
  setDraftFiles: Dispatch<SetStateAction<DraftAttachment[]>>;
  setDraftMessage: (message: string) => void;
  setIsBulkLaunching: (value: boolean) => void;
  setIsStreamHealthy: (value: boolean) => void;
  setPendingAssistantMessage: Dispatch<SetStateAction<PendingAssistantMessage | null>>;
  setPendingUserMessage: Dispatch<SetStateAction<PendingUserMessage | null>>;
  setPreviewAttachmentId: (id: string | null) => void;
  snapToBottom: () => void;
  threadDetail: AgentThreadDetail | undefined;
  upsertThreadSummary: (thread: AgentThreadSummary) => void;
}

export function useAgentComposerActions({
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
  setIsStreamHealthy,
  setPendingAssistantMessage,
  setPendingUserMessage,
  setPreviewAttachmentId,
  snapToBottom,
  threadDetail,
  upsertThreadSummary
}: UseAgentComposerActionsArgs) {
  const queryClient = useQueryClient();
  const { notify } = useNotifications();
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const sendAbortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      if (sendAbortControllerRef.current) {
        sendAbortControllerRef.current.abort();
        sendAbortControllerRef.current = null;
      }
    };
  }, []);

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

  return {
    handleStopRun,
    handleSubmitMessage,
    isSendingMessage
  };
}

/**
 * CALLING SPEC:
 * - Purpose: provide the `useAgentComposerActions` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/features/agent/panel/useAgentComposerActions.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `useAgentComposerActions`.
 * - Side effects: client-side state coordination and query wiring.
 */
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
import { type DraftAttachment, type PendingAssistantMessage, type PendingUserMessage, type ReadyDraftAttachment } from "./types";

interface UseAgentComposerActionsArgs {
  activeRunId: string | null;
  activeStreamRunId: string | null;
  addOptimisticRunningThreadId: (threadId: string) => void;
  bulkLaunchConcurrencyLimit: number;
  clearOptimisticThreadTitle: (threadId: string) => void;
  draftAttachments: DraftAttachment[];
  draftMessage: string;
  ensureThreadId: () => Promise<string>;
  handleAgentStreamEvent: (threadId: string, event: AgentStreamEvent) => void;
  interruptRun: (payload: { runId: string; threadId: string }) => Promise<void>;
  isBulkMode: boolean;
  removeOptimisticRunningThreadId: (threadId: string) => void;
  resetOptimisticRunState: (threadId?: string) => void;
  resolveDraftAttachmentsForSend: (attachments: DraftAttachment[]) => Promise<ReadyDraftAttachment[]>;
  selectedComposerModel: string;
  selectedThreadId: string;
  setActionError: (message: string | null) => void;
  setDraftAttachments: Dispatch<SetStateAction<DraftAttachment[]>>;
  setDraftMessage: (message: string) => void;
  setIsBulkLaunching: (value: boolean) => void;
  setPendingAssistantMessage: (threadId: string, message: PendingAssistantMessage | null) => void;
  setPendingUserMessage: (threadId: string, message: PendingUserMessage | null) => void;
  setThreadStreamHealthy: (threadId: string, isHealthy: boolean) => void;
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
  draftAttachments,
  draftMessage,
  ensureThreadId,
  handleAgentStreamEvent,
  interruptRun,
  isBulkMode,
  removeOptimisticRunningThreadId,
  resetOptimisticRunState,
  resolveDraftAttachmentsForSend,
  selectedComposerModel,
  selectedThreadId,
  setActionError,
  setDraftAttachments,
  setDraftMessage,
  setIsBulkLaunching,
  setPendingAssistantMessage,
  setPendingUserMessage,
  setThreadStreamHealthy,
  snapToBottom,
  threadDetail,
  upsertThreadSummary
}: UseAgentComposerActionsArgs) {
  const queryClient = useQueryClient();
  const { notify } = useNotifications();
  const [sendingThreadIds, setSendingThreadIds] = useState<string[]>([]);
  const sendAbortControllersRef = useRef<Record<string, AbortController>>({});

  useEffect(() => {
    return () => {
      Object.values(sendAbortControllersRef.current).forEach((controller) => controller.abort());
      sendAbortControllersRef.current = {};
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
      const readyAttachments = await resolveDraftAttachmentsForSend(attachments);
      const results = await mapWithConcurrency(readyAttachments, bulkLaunchConcurrencyLimit, async (attachment) => {
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
            files: [],
            attachmentIds: [attachment.uploadedAttachmentId],
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
      setDraftAttachments((current) => current.filter((attachment) => failedAttachmentIdSet.has(attachment.id)));
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
    let threadId: string | null = null;
    try {
      threadId = await ensureThreadId();
      const activeThreadId = threadId;
      const sendAbortController = new AbortController();
      sendAbortControllersRef.current[activeThreadId] = sendAbortController;
      setSendingThreadIds((current) => (current.includes(activeThreadId) ? current : [...current, activeThreadId]));
      addOptimisticRunningThreadId(activeThreadId);
      setThreadStreamHealthy(activeThreadId, true);
      resetOptimisticRunState(activeThreadId);
      invalidateAgentThreadData(queryClient, activeThreadId);
      const readyAttachments = await resolveDraftAttachmentsForSend(attachments);
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
        attachments: readyAttachments.map((item, index) => ({
          id: `${item.id}-${index}`,
          name: item.file.name,
          url: URL.createObjectURL(item.file),
          mimeType: item.file.type || "",
          kind: item.kind
        }))
      };
      setPendingUserMessage(activeThreadId, optimisticMessage);
      setPendingAssistantMessage(activeThreadId, {
        id: `pending-assistant-${Date.now()}`,
        threadId: activeThreadId,
        createdAt: new Date().toISOString(),
        baselineLastAssistantMessageId
      });
      setDraftMessage("");
      setDraftAttachments([]);
      snapToBottom();

      await streamAgentMessage({
        threadId: activeThreadId,
        content,
        files: [],
        attachmentIds: readyAttachments.map((item) => item.uploadedAttachmentId),
        modelName: selectedComposerModel || undefined,
        signal: sendAbortController.signal,
        onEvent: (streamEvent) => handleAgentStreamEvent(activeThreadId, streamEvent)
      });
      delete sendAbortControllersRef.current[activeThreadId];
      setThreadStreamHealthy(activeThreadId, false);
      const detail = await getAgentThread(activeThreadId);
      queryClient.setQueryData(queryKeys.agent.thread(activeThreadId), detail);
      clearOptimisticThreadTitle(activeThreadId);
      invalidateAgentThreadData(queryClient, activeThreadId);
      setPendingUserMessage(activeThreadId, null);
      setPendingAssistantMessage(activeThreadId, null);
      removeOptimisticRunningThreadId(activeThreadId);
      resetOptimisticRunState(activeThreadId);
    } catch (error) {
      if (threadId) {
        delete sendAbortControllersRef.current[threadId];
        setThreadStreamHealthy(threadId, false);
      }
      if ((error as Error).name === "AbortError") {
        if (threadId) {
          setPendingUserMessage(threadId, null);
          setPendingAssistantMessage(threadId, null);
          resetOptimisticRunState(threadId);
        }
        setActionError(null);
      } else {
        setActionError((error as Error).message);
      }
    } finally {
      if (threadId) {
        removeOptimisticRunningThreadId(threadId);
      }
      if (threadId) {
        setSendingThreadIds((current) => current.filter((item) => item !== threadId));
      }
    }
  }

  async function handleSubmitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionError(null);
    const content = draftMessage.trim();
    if (isBulkMode) {
      await handleSubmitBulkMessages(content, [...draftAttachments]);
      return;
    }
    if (!content && draftAttachments.length === 0) {
      setActionError("Enter a message or attach at least one file.");
      return;
    }
    await handleSubmitSingleMessage(content, [...draftAttachments]);
  }

  async function handleStopRun() {
    if (!selectedThreadId) {
      return;
    }
    setActionError(null);
    setThreadStreamHealthy(selectedThreadId, false);
    removeOptimisticRunningThreadId(selectedThreadId);
    setPendingAssistantMessage(selectedThreadId, null);
    setPendingUserMessage(selectedThreadId, null);
    resetOptimisticRunState(selectedThreadId);
    setSendingThreadIds((current) => current.filter((threadId) => threadId !== selectedThreadId));
    const abortController = sendAbortControllersRef.current[selectedThreadId];
    if (abortController) {
      abortController.abort();
      delete sendAbortControllersRef.current[selectedThreadId];
    }
    let runIdToInterrupt = activeRunId || activeStreamRunId || null;
    if (!runIdToInterrupt) {
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
      await interruptRun({ runId: runIdToInterrupt, threadId: selectedThreadId });
    } catch (error) {
      setActionError((error as Error).message);
    }
  }

  return {
    handleStopRun,
    handleSubmitMessage,
    sendingThreadIds
  };
}

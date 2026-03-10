import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { getAgentToolCall } from "../../../lib/api";
import { invalidateAgentThreadData } from "../../../lib/queryInvalidation";
import type { AgentRun, AgentRunEvent, AgentStreamEvent, AgentThreadDetail, AgentToolCall } from "../../../lib/types";
import { mergeRunToolCalls, runsWithoutAssistantMessage } from "../activity";
import { extractRenameThreadTitle } from "./helpers";
import type { PendingAssistantMessage } from "./types";

interface UseAgentComposerStreamStateArgs {
  applyThreadTitleToCaches: (threadId: string, title: string | null, updatedAt?: string) => void;
  pendingAssistantMessage: PendingAssistantMessage | null;
  selectedThreadId: string;
  setActionError: (message: string | null) => void;
  threadDetail: AgentThreadDetail | undefined;
}

export function useAgentComposerStreamState({
  applyThreadTitleToCaches,
  pendingAssistantMessage,
  selectedThreadId,
  setActionError,
  threadDetail
}: UseAgentComposerStreamStateArgs) {
  const queryClient = useQueryClient();
  const [activeStreamRunIdsByThreadId, setActiveStreamRunIdsByThreadId] = useState<Record<string, string>>({});
  const [streamedReasoningTextByRunId, setStreamedReasoningTextByRunId] = useState<Record<string, string>>({});
  const [streamedTextByRunId, setStreamedTextByRunId] = useState<Record<string, string>>({});
  const [optimisticRunEventsByRunId, setOptimisticRunEventsByRunId] = useState<Record<string, AgentRunEvent[]>>({});
  const [optimisticToolCallsByRunId, setOptimisticToolCallsByRunId] = useState<Record<string, AgentToolCall[]>>({});
  const [hydratingToolCallIds, setHydratingToolCallIds] = useState<Set<string>>(new Set());
  const activeStreamRunIdsRef = useRef<Record<string, string>>({});
  const threadRunsRef = useRef<AgentRun[]>([]);
  const optimisticToolCallsRef = useRef<Record<string, AgentToolCall[]>>({});
  const hydratingToolCallIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    activeStreamRunIdsRef.current = activeStreamRunIdsByThreadId;
  }, [activeStreamRunIdsByThreadId]);

  useEffect(() => {
    threadRunsRef.current = threadDetail?.runs ?? [];
  }, [threadDetail?.runs]);

  useEffect(() => {
    optimisticToolCallsRef.current = optimisticToolCallsByRunId;
  }, [optimisticToolCallsByRunId]);

  const pendingAssistantRuns = useMemo(() => runsWithoutAssistantMessage(threadDetail), [threadDetail]);
  const activeStreamRunId = selectedThreadId ? (activeStreamRunIdsByThreadId[selectedThreadId] ?? null) : null;
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
  const shouldShowOptimisticAssistantBubble = Boolean(
    pendingAssistantMessage && pendingAssistantMessage.threadId === selectedThreadId
  );
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

  const clearRunState = useCallback((runId: string) => {
    setStreamedReasoningTextByRunId((current) => {
      if (!(runId in current)) {
        return current;
      }
      const next = { ...current };
      delete next[runId];
      return next;
    });
    setStreamedTextByRunId((current) => {
      if (!(runId in current)) {
        return current;
      }
      const next = { ...current };
      delete next[runId];
      return next;
    });
    setOptimisticRunEventsByRunId((current) => {
      if (!(runId in current)) {
        return current;
      }
      const next = { ...current };
      delete next[runId];
      return next;
    });
    setOptimisticToolCallsByRunId((current) => {
      if (!(runId in current)) {
        return current;
      }
      const next = { ...current };
      delete next[runId];
      return next;
    });
  }, []);

  const resetOptimisticRunState = useCallback(
    (threadId?: string) => {
      if (!threadId) {
        setActiveStreamRunIdsByThreadId({});
        setStreamedReasoningTextByRunId({});
        setStreamedTextByRunId({});
        setOptimisticRunEventsByRunId({});
        setOptimisticToolCallsByRunId({});
        setHydratingToolCallIds(new Set());
        hydratingToolCallIdsRef.current.clear();
        return;
      }

      const runId = activeStreamRunIdsRef.current[threadId];
      if (!runId) {
        return;
      }
      setActiveStreamRunIdsByThreadId((current) => {
        if (!(threadId in current)) {
          return current;
        }
        const next = { ...current };
        delete next[threadId];
        return next;
      });
      clearRunState(runId);
    },
    [clearRunState]
  );

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

  const handleAgentStreamEvent = useCallback(
    (threadId: string, event: AgentStreamEvent) => {
      if (event.type === "run_event") {
        setActiveStreamRunIdsByThreadId((current) =>
          current[threadId] === event.run_id ? current : { ...current, [threadId]: event.run_id }
        );
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
        setActiveStreamRunIdsByThreadId((current) =>
          current[threadId] === event.run_id ? current : { ...current, [threadId]: event.run_id }
        );
        setStreamedReasoningTextByRunId((current) => ({
          ...current,
          [event.run_id]: `${current[event.run_id] ?? ""}${event.delta}`
        }));
        return;
      }
      if (event.type === "text_delta") {
        setActiveStreamRunIdsByThreadId((current) =>
          current[threadId] === event.run_id ? current : { ...current, [threadId]: event.run_id }
        );
        setStreamedTextByRunId((current) => ({
          ...current,
          [event.run_id]: `${current[event.run_id] ?? ""}${event.delta}`
        }));
      }
    },
    [hydrateToolCallDetails, queryClient, setActionError]
  );

  return {
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
  };
}

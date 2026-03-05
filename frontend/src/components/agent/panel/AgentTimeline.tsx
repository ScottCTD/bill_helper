import { Fragment, type RefObject } from "react";
import { ArrowDown, FileText } from "lucide-react";

import { withApiBase } from "../../../lib/api";
import type { AgentMessage, AgentRun, AgentRunEvent, AgentToolCall } from "../../../lib/types";
import { cn } from "../../../lib/utils";
import { AgentRunBlock, PendingAssistantActivityBlock } from "../AgentRunBlock";
import { MarkdownRenderer } from "../../ui/MarkdownRenderer";
import { prettyDateTime } from "./format";
import type { PendingAssistantMessage, PendingUserMessage } from "./types";

interface AgentTimelineProps {
  selectedThreadId: string;
  isLoading: boolean;
  errorMessage: string | null;
  messages: AgentMessage[] | undefined;
  timelineScrollRef: RefObject<HTMLDivElement | null>;
  runsByAssistantMessageId: Map<string, AgentRun[]>;
  pendingAssistantRuns: AgentRun[];
  pendingAssistantRunsByUserMessageId: Map<string, AgentRun[]>;
  pendingUserMessage: PendingUserMessage | null;
  pendingAssistantMessage: PendingAssistantMessage | null;
  shouldShowOptimisticAssistantBubble: boolean;
  pendingRunAttachedToOptimisticMessage: AgentRun | null;
  isMutating: boolean;
  activeStreamText: string;
  optimisticRunEventsByRunId: Record<string, AgentRunEvent[]>;
  optimisticToolCallsByRunId: Record<string, AgentToolCall[]>;
  activeOptimisticEvents: AgentRunEvent[];
  activeOptimisticToolCalls: AgentToolCall[];
  onHydrateToolCall: (runId: string, toolCallId: string) => void;
  hydratingToolCallIds: ReadonlySet<string>;
  onReviewRun: (runId: string | null) => void;
  isAtBottom: boolean;
  scrollToBottom: () => void;
}

export function AgentTimeline(props: AgentTimelineProps) {
  const {
    selectedThreadId,
    isLoading,
    errorMessage,
    messages,
    timelineScrollRef,
    runsByAssistantMessageId,
    pendingAssistantRuns,
    pendingAssistantRunsByUserMessageId,
    pendingUserMessage,
    pendingAssistantMessage,
    shouldShowOptimisticAssistantBubble,
    pendingRunAttachedToOptimisticMessage,
    isMutating,
    activeStreamText,
    optimisticRunEventsByRunId = {},
    optimisticToolCallsByRunId = {},
    activeOptimisticEvents = [],
    activeOptimisticToolCalls = [],
    onHydrateToolCall,
    hydratingToolCallIds,
    onReviewRun,
    isAtBottom,
    scrollToBottom
  } = props;

  function isImageMimeType(mimeType: string): boolean {
    return mimeType.toLowerCase().startsWith("image/");
  }

  function hasRenderableRunCard(run: AgentRun, optimisticEvents: AgentRunEvent[] = []): boolean {
    return Boolean(run.error_text) || run.events.length > 0 || run.change_items.length > 0 || optimisticEvents.length > 0;
  }

  return (
    <>
      {!selectedThreadId ? <p className="muted agent-timeline-empty">Create or select a thread to begin.</p> : null}
      {isLoading ? <p>Loading timeline...</p> : null}
      {errorMessage ? <p className="error">{errorMessage}</p> : null}

      {selectedThreadId ? (
        <div className="agent-timeline-scroll-wrapper">
          <div className="agent-timeline-scroll" ref={timelineScrollRef}>
          {(messages ?? []).map((message) => {
            const isAssistant = message.role === "assistant";
            const isUser = message.role === "user";
            const shouldRenderMarkdown = !isUser;
            const renderedContent = message.content_markdown;
            const messageRuns = isAssistant ? runsByAssistantMessageId.get(message.id) ?? [] : [];
            const userMessageRuns = isUser ? pendingAssistantRunsByUserMessageId.get(message.id) ?? [] : [];

            return (
              <Fragment key={message.id}>
                <article className={cn("agent-message", isAssistant && "agent-message-assistant", isUser && "agent-message-user")}>
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
                          onReviewRun={onReviewRun}
                          onHydrateToolCall={onHydrateToolCall}
                          hydratingToolCallIds={hydratingToolCallIds}
                          mode="activity"
                          optimisticEvents={optimisticRunEventsByRunId[run.id] ?? []}
                          optimisticToolCalls={optimisticToolCallsByRunId[run.id] ?? []}
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
                    <div className="agent-message-attachments">
                      {message.attachments.map((attachment) => (
                        isImageMimeType(attachment.mime_type) ? (
                          <img
                            key={attachment.id}
                            className="agent-message-attachment-image"
                            src={withApiBase(attachment.attachment_url)}
                            alt="User upload"
                            loading="lazy"
                          />
                        ) : (
                          <a
                            key={attachment.id}
                            className="agent-message-attachment-file"
                            href={withApiBase(attachment.attachment_url)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <FileText className="h-4 w-4" />
                            <span>{attachment.mime_type === "application/pdf" ? "Open PDF attachment" : "Open attachment"}</span>
                          </a>
                        )
                      ))}
                    </div>
                  ) : null}

                  {isAssistant
                    ? messageRuns.map((run) => (
                        <AgentRunBlock
                          key={`${run.id}-summary`}
                          run={run}
                          isMutating={isMutating}
                          onReviewRun={onReviewRun}
                          onHydrateToolCall={onHydrateToolCall}
                          hydratingToolCallIds={hydratingToolCallIds}
                          mode="summary"
                          optimisticEvents={optimisticRunEventsByRunId[run.id] ?? []}
                          optimisticToolCalls={optimisticToolCallsByRunId[run.id] ?? []}
                        />
                      ))
                    : null}
                </article>

                {isUser
                  ? userMessageRuns.map((run) => {
                      const optimisticEvents = optimisticRunEventsByRunId[run.id] ?? [];
                      if (!hasRenderableRunCard(run, optimisticEvents)) {
                        return null;
                      }
                      const attachedToOptimisticMessage = pendingRunAttachedToOptimisticMessage && pendingRunAttachedToOptimisticMessage.id === run.id;
                      if (attachedToOptimisticMessage) {
                        return null;
                      }
                      return (
                        <article key={`${run.id}-unattached`} className="agent-message agent-message-assistant agent-message-working">
                          <header>
                            <strong>Assistant</strong>
                            <span className="muted">{prettyDateTime(run.created_at)}</span>
                          </header>
                          <AgentRunBlock
                            run={run}
                            isMutating={isMutating}
                            onReviewRun={onReviewRun}
                            onHydrateToolCall={onHydrateToolCall}
                            hydratingToolCallIds={hydratingToolCallIds}
                            mode="activity"
                            optimisticEvents={optimisticEvents}
                            optimisticToolCalls={optimisticToolCallsByRunId[run.id] ?? []}
                          />
                        </article>
                      );
                    })
                  : null}
              </Fragment>
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
                <p className="muted">(attachment-only message)</p>
              )}
              {pendingUserMessage.attachments.length > 0 ? (
                <div className="agent-message-attachments">
                  {pendingUserMessage.attachments.map((attachment) => (
                    attachment.kind === "image" ? (
                      <img key={attachment.id} className="agent-message-attachment-image" src={attachment.url} alt={attachment.name} loading="lazy" />
                    ) : (
                      <a key={attachment.id} className="agent-message-attachment-file" href={attachment.url} target="_blank" rel="noreferrer">
                        <FileText className="h-4 w-4" />
                        <span>{attachment.name}</span>
                      </a>
                    )
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
                  onReviewRun={onReviewRun}
                  onHydrateToolCall={onHydrateToolCall}
                  hydratingToolCallIds={hydratingToolCallIds}
                  mode="activity"
                  optimisticEvents={activeOptimisticEvents}
                  optimisticToolCalls={activeOptimisticToolCalls}
                  streamingAssistantText={activeStreamText}
                />
              ) : activeOptimisticEvents.length > 0 || activeStreamText.length > 0 ? (
                <PendingAssistantActivityBlock
                  events={activeOptimisticEvents}
                  toolCalls={activeOptimisticToolCalls}
                  onHydrateToolCall={onHydrateToolCall}
                  hydratingToolCallIds={hydratingToolCallIds}
                  streamingAssistantText={activeStreamText}
                />
              ) : null}
              {!activeStreamText.length && activeOptimisticEvents.length === 0 && !pendingRunAttachedToOptimisticMessage ? (
                <p className="agent-message-text agent-message-streaming-text">
                  <span className="agent-message-caret">{"\u258d"}</span>
                </p>
              ) : null}
            </article>
          ) : null}

          {pendingAssistantRuns.map((run) => {
            const optimisticEvents = optimisticRunEventsByRunId[run.id] ?? [];
            const attachedToOptimisticMessage = pendingRunAttachedToOptimisticMessage && pendingRunAttachedToOptimisticMessage.id === run.id;
            const alreadyAnchoredToUserMessage = Boolean(
              (messages ?? []).some((message) => message.id === run.user_message_id)
            );
            if (attachedToOptimisticMessage) {
              return null;
            }
            if (alreadyAnchoredToUserMessage) {
              return null;
            }
            if (!hasRenderableRunCard(run, optimisticEvents)) {
              return null;
            }
            return (
              <article key={`pending-run-${run.id}`} className="agent-message agent-message-assistant agent-message-working">
                <header>
                  <strong>Assistant</strong>
                  <span className="muted">{prettyDateTime(run.created_at)}</span>
                </header>
                <AgentRunBlock
                  run={run}
                  isMutating={isMutating}
                  onReviewRun={onReviewRun}
                  onHydrateToolCall={onHydrateToolCall}
                  hydratingToolCallIds={hydratingToolCallIds}
                  optimisticEvents={optimisticEvents}
                  optimisticToolCalls={optimisticToolCallsByRunId[run.id] ?? []}
                />
              </article>
            );
          })}
          </div>
          {!isAtBottom ? (
            <button
              type="button"
              className="agent-scroll-to-bottom"
              onClick={scrollToBottom}
              aria-label="Scroll to bottom"
            >
              <ArrowDown className="h-4 w-4" />
            </button>
          ) : null}
        </div>
      ) : null}
    </>
  );
}

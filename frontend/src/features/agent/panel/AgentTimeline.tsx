/**
 * CALLING SPEC:
 * - Purpose: render the `AgentTimeline` React UI module.
 * - Inputs: callers that import `frontend/src/features/agent/panel/AgentTimeline.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `AgentTimeline`.
 * - Side effects: React rendering and user event wiring.
 */
import { Fragment, memo, type Ref } from "react";
import { ArrowDown, File, FileImage, FileText } from "lucide-react";

import type { AgentMessage, AgentRun, AgentRunEvent, AgentToolCall } from "../../../lib/types";
import { cn } from "../../../lib/utils";
import { AgentRunBlock, PendingAssistantActivityBlock } from "../AgentRunBlock";
import { MarkdownRenderer } from "../../../components/ui/MarkdownRenderer";
import { AgentAttachmentImageCard } from "./AgentAttachmentImageCard";
import { AgentAttachmentPdfCard } from "./AgentAttachmentPdfCard";
import { AgentAttachmentFileRow } from "./AgentAttachmentFileRow";
import { AgentMessageAttachmentRow } from "./AgentMessageAttachmentRow";
import { AgentMessageAttachmentImage } from "./AgentMessageAttachmentImage";
import { AgentMessageAttachmentPdf } from "./AgentMessageAttachmentPdf";
import { openAttachmentInNewTab } from "./attachmentBrowserOpen";
import { prettyDateTime } from "./format";
import type { PendingAssistantMessage, PendingUserMessage } from "./types";

export interface AgentTimelineProps {
  selectedThreadId: string;
  isLoading: boolean;
  errorMessage: string | null;
  messages: AgentMessage[] | undefined;
  timelineScrollRef: Ref<HTMLDivElement>;
  runsByAssistantMessageId: Map<string, AgentRun[]>;
  pendingAssistantRuns: AgentRun[];
  pendingAssistantRunsByUserMessageId: Map<string, AgentRun[]>;
  pendingUserMessage: PendingUserMessage | null;
  pendingAssistantMessage: PendingAssistantMessage | null;
  shouldShowOptimisticAssistantBubble: boolean;
  pendingRunAttachedToOptimisticMessage: AgentRun | null;
  isMutating: boolean;
  activeStreamReasoningText: string;
  activeStreamText: string;
  optimisticRunEventsByRunId: Record<string, AgentRunEvent[]>;
  optimisticToolCallsByRunId: Record<string, AgentToolCall[]>;
  activeOptimisticEvents: AgentRunEvent[];
  activeOptimisticToolCalls: AgentToolCall[];
  detachFromBottom: () => void;
  onHydrateToolCall: (runId: string, toolCallId: string) => void;
  hydratingToolCallIds: ReadonlySet<string>;
  isAtBottom: boolean;
  scrollToBottom: () => void;
}

function AgentTimelineComponent(props: AgentTimelineProps) {
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
    activeStreamReasoningText,
    activeStreamText,
    optimisticRunEventsByRunId = {},
    optimisticToolCallsByRunId = {},
    activeOptimisticEvents = [],
    activeOptimisticToolCalls = [],
    detachFromBottom,
    onHydrateToolCall,
    hydratingToolCallIds,
    isAtBottom,
    scrollToBottom
  } = props;

  function isImageMimeType(mimeType: string): boolean {
    return mimeType.toLowerCase().startsWith("image/");
  }

  function isPdfMimeType(mimeType: string): boolean {
    return mimeType.toLowerCase() === "application/pdf";
  }

  function hasRenderableRunCard(run: AgentRun, optimisticEvents: AgentRunEvent[] = []): boolean {
    return Boolean(run.error_text) || run.events.length > 0 || run.change_items.length > 0 || optimisticEvents.length > 0;
  }

  function renderAssistantAttachments(attachments: AgentMessage["attachments"]) {
    if (attachments.length === 0) {
      return null;
    }

    return (
      <div className="agent-message-attachments">
        {attachments.map((attachment) => (
          "message_id" in attachment ? (
            isImageMimeType(attachment.mime_type) ? (
              <AgentMessageAttachmentImage
                key={attachment.id}
                attachmentUrl={attachment.attachment_url}
                alt={attachment.display_name}
              />
            ) : isPdfMimeType(attachment.mime_type) ? (
              <AgentMessageAttachmentPdf
                key={attachment.id}
                attachmentUrl={attachment.attachment_url}
                title={attachment.display_name}
              />
            ) : (
              <div
                key={attachment.id}
                className="agent-message-attachment-file"
              >
                <FileText className="h-4 w-4" />
                <span>{attachment.display_name}</span>
              </div>
            )
          ) : attachment.kind === "image" ? (
            <AgentAttachmentImageCard key={attachment.id} previewUrl={attachment.url} alt={attachment.name} />
          ) : attachment.kind === "pdf" ? (
            <AgentAttachmentPdfCard key={attachment.id} previewUrl={attachment.url} title={attachment.name} />
          ) : (
            <div key={attachment.id} className="agent-message-attachment-file">
              <FileText className="h-4 w-4" />
              <span>{attachment.name}</span>
            </div>
          )
        ))}
      </div>
    );
  }

  function renderUserAttachments(
    attachments: AgentMessage["attachments"] | PendingUserMessage["attachments"]
  ) {
    if (attachments.length === 0) {
      return null;
    }

    return (
      <div className="agent-message-user-attachments">
        {attachments.map((attachment) => (
          "message_id" in attachment ? (
            <AgentMessageAttachmentRow
              key={attachment.id}
              attachmentUrl={attachment.attachment_url}
              fileLabel={attachment.display_name}
              mimeType={attachment.mime_type}
            />
          ) : (
            <AgentAttachmentFileRow
              key={attachment.id}
              fileLabel={attachment.name}
              icon={
                attachment.kind === "image"
                  ? FileImage
                  : attachment.kind === "pdf"
                    ? FileText
                    : File
              }
              onOpen={() => openAttachmentInNewTab(attachment.url)}
            />
          )
        ))}
      </div>
    );
  }

  function renderUserBubble(options: {
    createdAt: string;
    text: string;
    emptyText: string;
    attachments: AgentMessage["attachments"] | PendingUserMessage["attachments"];
  }) {
    return (
      <>
        <header className="agent-message-header agent-message-user-meta">
          <span className="muted">{prettyDateTime(options.createdAt)}</span>
        </header>
        <div className="agent-message-user-bubble">
          {renderUserAttachments(options.attachments)}
          {options.text ? (
            <p className="agent-message-text">{options.text}</p>
          ) : (
            <p className="muted">{options.emptyText}</p>
          )}
        </div>
      </>
    );
  }

  function messageClassName(options: {
    isAssistant?: boolean;
    isUser?: boolean;
    isActivity?: boolean;
    isStreaming?: boolean;
  }): string {
    return cn(
      "agent-message",
      options.isAssistant && "agent-message-assistant",
      options.isUser && "agent-message-user",
      options.isActivity && "agent-message-activity",
      options.isStreaming && "agent-message-streaming"
    );
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
                <article
                  className={messageClassName({
                    isAssistant,
                    isUser,
                    isActivity: messageRuns.length > 0
                  })}
                >
                  {isUser ? (
                    renderUserBubble({
                      createdAt: message.created_at,
                      text: renderedContent,
                      emptyText: "(no text)",
                      attachments: message.attachments
                    })
                  ) : (
                    <>
                      <header className="agent-message-header agent-message-meta-only">
                        <span className="muted">{prettyDateTime(message.created_at)}</span>
                      </header>

                      {isAssistant
                        ? messageRuns.map((run) => (
                            <AgentRunBlock
                              key={`${run.id}-activity`}
                              run={run}
                              isMutating={isMutating}
                              onInspectActivity={detachFromBottom}
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

                      {renderAssistantAttachments(message.attachments)}

                      {isAssistant
                        ? messageRuns.map((run) => (
                            <AgentRunBlock
                              key={`${run.id}-summary`}
                              run={run}
                              isMutating={isMutating}
                              onInspectActivity={detachFromBottom}
                              onHydrateToolCall={onHydrateToolCall}
                              hydratingToolCallIds={hydratingToolCallIds}
                              mode="summary"
                              optimisticEvents={optimisticRunEventsByRunId[run.id] ?? []}
                              optimisticToolCalls={optimisticToolCallsByRunId[run.id] ?? []}
                            />
                          ))
                        : null}
                    </>
                  )}
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
                        <article
                          key={`${run.id}-unattached`}
                          className={messageClassName({
                            isAssistant: true,
                            isActivity: true
                          })}
                        >
                          <header className="agent-message-header agent-message-meta-only">
                            <span className="muted">{prettyDateTime(run.created_at)}</span>
                          </header>
                          <AgentRunBlock
                            run={run}
                            isMutating={isMutating}
                            onInspectActivity={detachFromBottom}
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
            <article className={messageClassName({ isUser: true })} key={pendingUserMessage.id}>
              {renderUserBubble({
                createdAt: pendingUserMessage.createdAt,
                text: pendingUserMessage.content,
                emptyText: "(attachment-only message)",
                attachments: pendingUserMessage.attachments
              })}
            </article>
          ) : null}

          {shouldShowOptimisticAssistantBubble && pendingAssistantMessage ? (
            <article
              className={messageClassName({
                isAssistant: true,
                isActivity: true,
                isStreaming: true
              })}
              key={pendingAssistantMessage.id}
            >
              <header className="agent-message-header agent-message-meta-only">
                <span className="muted">{prettyDateTime(pendingAssistantMessage.createdAt)}</span>
              </header>
              {pendingRunAttachedToOptimisticMessage ? (
                <AgentRunBlock
                  run={pendingRunAttachedToOptimisticMessage}
                  isMutating={isMutating}
                  onInspectActivity={detachFromBottom}
                  onHydrateToolCall={onHydrateToolCall}
                  hydratingToolCallIds={hydratingToolCallIds}
                  mode="activity"
                  optimisticEvents={activeOptimisticEvents}
                  optimisticToolCalls={activeOptimisticToolCalls}
                  streamingReasoningText={activeStreamReasoningText}
                  streamingAssistantText={activeStreamText}
                />
              ) : activeOptimisticEvents.length > 0 || activeStreamReasoningText.length > 0 || activeStreamText.length > 0 ? (
                <PendingAssistantActivityBlock
                  events={activeOptimisticEvents}
                  toolCalls={activeOptimisticToolCalls}
                  onInspectActivity={detachFromBottom}
                  onHydrateToolCall={onHydrateToolCall}
                  hydratingToolCallIds={hydratingToolCallIds}
                  streamingReasoningText={activeStreamReasoningText}
                  streamingAssistantText={activeStreamText}
                />
              ) : null}
              {!activeStreamReasoningText.length &&
              !activeStreamText.length &&
              activeOptimisticEvents.length === 0 &&
              !pendingRunAttachedToOptimisticMessage ? (
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
              <article
                key={`pending-run-${run.id}`}
                className={messageClassName({
                  isAssistant: true,
                  isActivity: true
                })}
              >
                <header className="agent-message-header agent-message-meta-only">
                  <span className="muted">{prettyDateTime(run.created_at)}</span>
                </header>
                <AgentRunBlock
                  run={run}
                  isMutating={isMutating}
                  onInspectActivity={detachFromBottom}
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

export const AgentTimeline = memo(AgentTimelineComponent);

AgentTimeline.displayName = "AgentTimeline";

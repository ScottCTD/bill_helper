import type { ChangeEvent, ClipboardEvent, DragEvent, FormEvent, KeyboardEvent, RefObject } from "react";
import { FileText, Paperclip, SendHorizontal, Square, X } from "lucide-react";

import { cn } from "../../../lib/utils";
import { Button } from "../../ui/button";
import { Textarea } from "../../ui/textarea";
import type { DraftAttachmentPreview } from "./types";

interface AgentComposerProps {
  isComposerDragActive: boolean;
  draftAttachmentPreviews: DraftAttachmentPreview[];
  previewAttachmentId: string | null;
  setPreviewAttachmentId: (id: string | null) => void;
  onRemoveAttachment: (attachmentId: string) => void;
  composerTextareaRef: RefObject<HTMLTextAreaElement | null>;
  fileInputRef: RefObject<HTMLInputElement | null>;
  draftMessage: string;
  isMutating: boolean;
  isRunInFlight: boolean;
  isSendingMessage: boolean;
  isInterruptPending: boolean;
  actionError: string | null;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onDragEnter: (event: DragEvent<HTMLFormElement>) => void;
  onDragOver: (event: DragEvent<HTMLFormElement>) => void;
  onDragLeave: (event: DragEvent<HTMLFormElement>) => void;
  onDrop: (event: DragEvent<HTMLFormElement>) => void;
  onMessageChange: (event: ChangeEvent<HTMLTextAreaElement>) => void;
  onComposerKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onComposerPaste: (event: ClipboardEvent<HTMLTextAreaElement>) => void;
  onFileSelection: (event: ChangeEvent<HTMLInputElement>) => void;
  onStopRun: () => void;
}

export function AgentComposer(props: AgentComposerProps) {
  const {
    isComposerDragActive,
    draftAttachmentPreviews,
    previewAttachmentId,
    setPreviewAttachmentId,
    onRemoveAttachment,
    composerTextareaRef,
    fileInputRef,
    draftMessage,
    isMutating,
    isRunInFlight,
    isSendingMessage,
    isInterruptPending,
    actionError,
    onSubmit,
    onDragEnter,
    onDragOver,
    onDragLeave,
    onDrop,
    onMessageChange,
    onComposerKeyDown,
    onComposerPaste,
    onFileSelection,
    onStopRun
  } = props;

  return (
    <form
      className={cn("agent-composer", isComposerDragActive && "agent-composer-drop-active")}
      onSubmit={onSubmit}
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {isComposerDragActive ? <p className="muted">Drop images or PDFs to attach</p> : null}
      {draftAttachmentPreviews.length > 0 ? (
        <div className="agent-draft-attachments" aria-label="Pending attachments">
          {draftAttachmentPreviews.map((preview) => (
            <div
              key={preview.id}
              className={cn("agent-draft-attachment-chip", preview.kind === "pdf" && "agent-draft-attachment-chip-file")}
            >
              {preview.kind === "image" ? (
                <button
                  type="button"
                  className="agent-draft-attachment-preview"
                  onClick={() => setPreviewAttachmentId(preview.id)}
                  title={preview.file.name}
                  aria-pressed={previewAttachmentId === preview.id}
                >
                  <img src={preview.url} alt={preview.file.name} loading="lazy" />
                </button>
              ) : (
                <button
                  type="button"
                  className="agent-draft-attachment-file"
                  onClick={() => setPreviewAttachmentId(preview.id)}
                  title={preview.file.name}
                  aria-pressed={previewAttachmentId === preview.id}
                >
                  <FileText className="h-4 w-4" />
                  <span className="agent-draft-attachment-file-name">{preview.file.name}</span>
                </button>
              )}
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="agent-draft-attachment-remove !size-4"
                onClick={() => onRemoveAttachment(preview.id)}
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
          onChange={onMessageChange}
          onKeyDown={onComposerKeyDown}
          onPaste={onComposerPaste}
          rows={1}
        />

        <div className="agent-composer-toolbar">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,application/pdf,.pdf"
            multiple
            onChange={onFileSelection}
            className="sr-only"
            tabIndex={-1}
          />
          <Button type="button" variant="ghost" size="sm" className="agent-composer-attach" onClick={() => fileInputRef.current?.click()}>
            <Paperclip className="h-4 w-4" />
            Add Attachments
          </Button>

          {isRunInFlight ? (
            <Button type="button" size="sm" variant="destructive" disabled={isInterruptPending} className="agent-composer-send" onClick={onStopRun}>
              {isInterruptPending ? "Stopping..." : "Stop"}
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
  );
}

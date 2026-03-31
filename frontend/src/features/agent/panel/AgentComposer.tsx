/**
 * CALLING SPEC:
 * - Purpose: render the `AgentComposer` React UI module.
 * - Inputs: callers that import `frontend/src/features/agent/panel/AgentComposer.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `AgentComposer`.
 * - Side effects: React rendering and user event wiring.
 */
import type { ChangeEvent, ClipboardEvent, DragEvent, FormEvent, KeyboardEvent, RefObject } from "react";
import { CircleHelp, FileImage, FileText, LoaderCircle, Paperclip, SendHorizontal, Square, X } from "lucide-react";

import { cn } from "../../../lib/utils";
import { Button } from "../../../components/ui/button";
import { Switch } from "../../../components/ui/switch";
import { Textarea } from "../../../components/ui/textarea";
import { Tooltip } from "../../../components/ui/tooltip";
import { resolveAgentModelOptionLabel } from "./helpers";
import type { DraftAttachment } from "./types";

interface AgentComposerProps {
  isComposerDragActive: boolean;
  draftAttachments: DraftAttachment[];
  onRemoveAttachment: (attachmentId: string) => void;
  composerTextareaRef: RefObject<HTMLTextAreaElement | null>;
  fileInputRef: RefObject<HTMLInputElement | null>;
  draftMessage: string;
  availableModels: string[];
  modelDisplayNames: Record<string, string>;
  selectedModel: string;
  attachmentsUseOcr: boolean;
  isAttachmentsUseOcrDisabled: boolean;
  isModelPickerDisabled: boolean;
  isMutating: boolean;
  isRunInFlight: boolean;
  isSendingMessage: boolean;
  isBulkMode: boolean;
  isBulkLaunching: boolean;
  isInterruptPending: boolean;
  bulkModeHelpText: string;
  actionError: string | null;
  onAttachmentsUseOcrChange: (checked: boolean) => void;
  onBulkModeChange: (checked: boolean) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onDragEnter: (event: DragEvent<HTMLFormElement>) => void;
  onDragOver: (event: DragEvent<HTMLFormElement>) => void;
  onDragLeave: (event: DragEvent<HTMLFormElement>) => void;
  onDrop: (event: DragEvent<HTMLFormElement>) => void;
  onMessageChange: (event: ChangeEvent<HTMLTextAreaElement>) => void;
  onModelChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  onComposerKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onComposerPaste: (event: ClipboardEvent<HTMLTextAreaElement>) => void;
  onFileSelection: (event: ChangeEvent<HTMLInputElement>) => void;
  onStopRun: () => void;
}

export function AgentComposer(props: AgentComposerProps) {
  const {
    isComposerDragActive,
    draftAttachments,
    onRemoveAttachment,
    composerTextareaRef,
    fileInputRef,
    draftMessage,
    availableModels,
    modelDisplayNames,
    selectedModel,
    attachmentsUseOcr,
    isAttachmentsUseOcrDisabled,
    isModelPickerDisabled,
    isMutating,
    isRunInFlight,
    isSendingMessage,
    isBulkMode,
    isBulkLaunching,
    isInterruptPending,
    bulkModeHelpText,
    actionError,
    onAttachmentsUseOcrChange,
    onBulkModeChange,
    onSubmit,
    onDragEnter,
    onDragOver,
    onDragLeave,
    onDrop,
    onMessageChange,
    onModelChange,
    onComposerKeyDown,
    onComposerPaste,
    onFileSelection,
    onStopRun
  } = props;
  const showStopButton = !isBulkMode && isRunInFlight;
  const submitLabel = isBulkLaunching ? "Starting..." : isSendingMessage ? "Sending..." : "Send";
  const composerPlaceholder = isBulkMode
    ? "Enter one shared prompt. Each attached file will start its own fresh thread."
    : "Ask a question or ask the agent to propose entries/tags/entities...";

  function attachmentStatusLabel(attachment: DraftAttachment): string | null {
    if (attachment.phase === "uploading") {
      return `${attachment.uploadProgress}%`;
    }
    if (attachment.phase === "parsing") {
      return "Parsing…";
    }
    if (attachment.phase === "processing") {
      return attachment.kind === "pdf" ? "Preparing pages…" : "Saving…";
    }
    if (attachment.phase === "ready") {
      return "Ready";
    }
    if (attachment.phase === "failed") {
      return attachment.errorMessage || "Upload failed.";
    }
    return null;
  }

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
      {draftAttachments.length > 0 ? (
        <div className="agent-draft-attachments scroll-surface" aria-label="Pending attachments">
          {draftAttachments.map((attachment) => (
            <div
              key={attachment.id}
              className={cn(
                "agent-draft-attachment-card",
                attachment.phase === "failed" && "agent-draft-attachment-card-failed"
              )}
            >
              <div className="agent-draft-attachment-card-top">
                <div className="agent-draft-attachment-file" title={attachment.file.name}>
                  {attachment.kind === "image" ? <FileImage className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
                  <span className="agent-draft-attachment-file-name">{attachment.file.name}</span>
                </div>
                <span className="agent-draft-attachment-inline-status">
                  {attachment.phase === "parsing" || attachment.phase === "processing" ? (
                    <span className="agent-draft-attachment-inline-label agent-draft-attachment-status-live">
                      <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                      {attachmentStatusLabel(attachment)}
                    </span>
                  ) : attachment.phase === "failed" ? (
                    <span className="agent-draft-attachment-inline-label agent-draft-attachment-inline-label-error">
                      {attachmentStatusLabel(attachment)}
                    </span>
                  ) : null}
                  {attachment.phase === "uploading" || attachment.phase === "ready" ? (
                    <span className="agent-draft-attachment-inline-label">{attachmentStatusLabel(attachment)}</span>
                  ) : null}
                  <span className="agent-draft-attachment-progress" aria-hidden="true">
                    <span
                      className={cn(
                        "agent-draft-attachment-progress-bar",
                        (attachment.phase === "parsing" || attachment.phase === "processing") && "is-parsing",
                        attachment.phase === "ready" && "is-ready",
                        attachment.phase === "failed" && "is-failed"
                      )}
                      style={
                        attachment.phase === "uploading"
                          ? { width: `${Math.max(6, attachment.uploadProgress)}%` }
                          : attachment.phase === "ready"
                            ? { width: "100%" }
                            : undefined
                      }
                    />
                  </span>
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="agent-draft-attachment-remove"
                  onClick={() => onRemoveAttachment(attachment.id)}
                  aria-label={`Remove ${attachment.file.name}`}
                  disabled={isSendingMessage || isBulkLaunching}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="agent-composer-box">
        <Textarea
          ref={composerTextareaRef}
          className="agent-composer-textarea border-none shadow-none focus-visible:ring-0"
          placeholder={composerPlaceholder}
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
          <div className="agent-composer-secondary-actions">
            <Button type="button" variant="ghost" size="sm" className="agent-composer-attach" onClick={() => fileInputRef.current?.click()}>
              <Paperclip className="h-4 w-4" />
              Add Attachments
            </Button>

            <label className="agent-composer-bulk-toggle">
              <Switch
                checked={isBulkMode}
                onCheckedChange={onBulkModeChange}
                disabled={isMutating || isSendingMessage || isBulkLaunching || isInterruptPending}
                aria-label="Bulk mode"
              />
              <span className="agent-composer-bulk-toggle-label">Bulk mode</span>
              <Tooltip content={bulkModeHelpText}>
                <button type="button" className="agent-composer-bulk-tooltip-trigger" aria-label="Bulk mode help">
                  <CircleHelp className="h-3.5 w-3.5 text-muted-foreground/80" aria-hidden="true" />
                </button>
              </Tooltip>
            </label>
            {draftAttachments.length > 0 ? (
              <label className="agent-composer-bulk-toggle">
                <Switch
                  checked={attachmentsUseOcr}
                  onCheckedChange={onAttachmentsUseOcrChange}
                  disabled={isAttachmentsUseOcrDisabled}
                  aria-label="Use OCR for attachments"
                />
                <span className="agent-composer-bulk-toggle-label">OCR</span>
              </label>
            ) : null}
          </div>

          <div className="agent-composer-primary-actions">
            <select
              className="agent-composer-model-select"
              aria-label="Agent model"
              value={availableModels.length === 0 ? "" : selectedModel}
              onChange={onModelChange}
              disabled={isModelPickerDisabled || availableModels.length === 0}
            >
              {availableModels.length === 0 ? <option value="">Loading models…</option> : null}
              {availableModels.map((modelName) => (
                <option key={modelName} value={modelName}>
                  {resolveAgentModelOptionLabel(modelName, modelDisplayNames)}
                </option>
              ))}
            </select>

            {showStopButton ? (
              <Button
                type="button"
                size="sm"
                variant="destructive"
                disabled={isInterruptPending}
                className="agent-composer-send"
                onClick={onStopRun}
              >
                {isInterruptPending ? "Stopping..." : "Stop"}
                <Square className="h-3.5 w-3.5" />
              </Button>
            ) : (
              <Button type="submit" size="sm" disabled={isMutating || isBulkLaunching} className="agent-composer-send">
                {submitLabel}
                <SendHorizontal className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
      {actionError ? <p className="error">{actionError}</p> : null}
    </form>
  );
}

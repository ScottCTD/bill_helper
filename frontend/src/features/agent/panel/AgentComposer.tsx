/**
 * CALLING SPEC:
 * - Purpose: render the `AgentComposer` React UI module.
 * - Inputs: callers that import `frontend/src/features/agent/panel/AgentComposer.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `AgentComposer`.
 * - Side effects: React rendering and user event wiring.
 */
import type { ChangeEvent, ClipboardEvent, DragEvent, FormEvent, KeyboardEvent, RefObject } from "react";
import { CircleHelp, FileText, Paperclip, SendHorizontal, Square, X } from "lucide-react";

import { cn } from "../../../lib/utils";
import { Button } from "../../../components/ui/button";
import { Switch } from "../../../components/ui/switch";
import { Textarea } from "../../../components/ui/textarea";
import { Tooltip } from "../../../components/ui/tooltip";
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
  availableModels: string[];
  selectedModel: string;
  isModelPickerDisabled: boolean;
  isMutating: boolean;
  isRunInFlight: boolean;
  isSendingMessage: boolean;
  isBulkMode: boolean;
  isBulkLaunching: boolean;
  isInterruptPending: boolean;
  bulkModeHelpText: string;
  actionError: string | null;
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
    draftAttachmentPreviews,
    previewAttachmentId,
    setPreviewAttachmentId,
    onRemoveAttachment,
    composerTextareaRef,
    fileInputRef,
    draftMessage,
    availableModels,
    selectedModel,
    isModelPickerDisabled,
    isMutating,
    isRunInFlight,
    isSendingMessage,
    isBulkMode,
    isBulkLaunching,
    isInterruptPending,
    bulkModeHelpText,
    actionError,
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
                  {modelName}
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

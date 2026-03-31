/**
 * CALLING SPEC:
 * - Purpose: provide the `useAgentDraftAttachments` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/features/agent/panel/useAgentDraftAttachments.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `useAgentDraftAttachments`.
 * - Side effects: client-side attachment upload/parsing coordination plus local object URL lifecycle.
 */
import {
  type ChangeEvent,
  type ClipboardEvent,
  type DragEvent,
  useEffect,
  useRef,
  useState
} from "react";

import { deleteAgentDraftAttachment, uploadAgentDraftAttachment } from "../../../lib/api";
import { detectDraftAttachmentKind, isSupportedAgentAttachment, type DraftAttachment, type ReadyDraftAttachment } from "./types";

interface UseAgentDraftAttachmentsArgs {
  setActionError: (message: string | null) => void;
  attachmentsUseOcr: boolean;
}

export function useAgentDraftAttachments(args: UseAgentDraftAttachmentsArgs) {
  const { setActionError, attachmentsUseOcr } = args;
  const [draftAttachments, setDraftAttachments] = useState<DraftAttachment[]>([]);
  const [isComposerDragActive, setIsComposerDragActive] = useState(false);

  const draftFileIdCounterRef = useRef(0);
  const composerDragDepthRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadAbortControllersRef = useRef<Record<string, AbortController>>({});
  const uploadPromisesRef = useRef<Record<string, Promise<ReadyDraftAttachment>>>({});
  const previousAttachmentsRef = useRef<Record<string, DraftAttachment>>({});

  useEffect(() => {
    const previousAttachments = previousAttachmentsRef.current;
    const nextAttachments = Object.fromEntries(draftAttachments.map((attachment) => [attachment.id, attachment]));
    Object.entries(previousAttachments).forEach(([attachmentId, attachment]) => {
      if (!(attachmentId in nextAttachments)) {
        delete uploadAbortControllersRef.current[attachmentId];
        delete uploadPromisesRef.current[attachmentId];
        URL.revokeObjectURL(attachment.localObjectUrl);
      }
    });
    previousAttachmentsRef.current = nextAttachments;
  }, [draftAttachments]);

  useEffect(() => {
    return () => {
      Object.values(uploadAbortControllersRef.current).forEach((controller) => controller.abort());
      Object.values(previousAttachmentsRef.current).forEach((attachment) => {
        URL.revokeObjectURL(attachment.localObjectUrl);
      });
    };
  }, []);

  function nextDraftAttachmentId(): string {
    draftFileIdCounterRef.current += 1;
    return `draft-attachment-${draftFileIdCounterRef.current}`;
  }

  function updateDraftAttachment(attachmentId: string, updater: (current: DraftAttachment) => DraftAttachment): void {
    setDraftAttachments((current) =>
      current.map((attachment) => (attachment.id === attachmentId ? updater(attachment) : attachment))
    );
  }

  function startDraftAttachmentUpload(attachment: DraftAttachment): void {
    const abortController = new AbortController();
    uploadAbortControllersRef.current[attachment.id] = abortController;
    const uploadPromise = (async () => {
      const uploadedAttachment = await uploadAgentDraftAttachment({
        file: attachment.file,
        useOcr: attachment.useOcr,
        signal: abortController.signal,
        onUploadProgress: (progressPercent) => {
          updateDraftAttachment(attachment.id, (current) => ({
            ...current,
            phase: "uploading",
            uploadProgress: progressPercent
          }));
        },
        onServerProcessingStart: () => {
          updateDraftAttachment(attachment.id, (current) => ({
            ...current,
            phase: attachment.useOcr ? "parsing" : "processing",
            uploadProgress: 100
          }));
        }
      });

      const readyAttachment: ReadyDraftAttachment = {
        id: attachment.id,
        file: attachment.file,
        kind: attachment.kind,
        localObjectUrl: attachment.localObjectUrl,
        uploadedAttachmentId: uploadedAttachment.id
      };

      updateDraftAttachment(attachment.id, (current) => ({
        ...current,
        phase: "ready",
        uploadProgress: 100,
        uploadedAttachmentId: uploadedAttachment.id,
        errorMessage: null
      }));
      delete uploadAbortControllersRef.current[attachment.id];
      return readyAttachment;
    })().catch((error: Error) => {
      delete uploadAbortControllersRef.current[attachment.id];
      if (error.name === "AbortError") {
        throw error;
      }
      updateDraftAttachment(attachment.id, (current) => ({
        ...current,
        phase: "failed",
        errorMessage: error.message
      }));
      throw error;
    });
    uploadPromise.catch(() => undefined);
    uploadPromisesRef.current[attachment.id] = uploadPromise;
  }

  function restartDraftAttachmentUpload(attachmentId: string, nextUseOcr: boolean): void {
    const currentAttachment = previousAttachmentsRef.current[attachmentId];
    if (!currentAttachment) {
      return;
    }
    uploadAbortControllersRef.current[attachmentId]?.abort();
    delete uploadAbortControllersRef.current[attachmentId];
    delete uploadPromisesRef.current[attachmentId];
    if (currentAttachment.uploadedAttachmentId) {
      void deleteAgentDraftAttachment(currentAttachment.uploadedAttachmentId).catch((error: Error) => {
        setActionError(error.message);
      });
    }
    const restartedAttachment: DraftAttachment = {
      ...currentAttachment,
      uploadedAttachmentId: null,
      uploadProgress: 0,
      phase: "uploading",
      errorMessage: null,
      useOcr: nextUseOcr
    };
    updateDraftAttachment(attachmentId, () => restartedAttachment);
    startDraftAttachmentUpload(restartedAttachment);
  }

  function appendDraftAttachments(files: File[]): void {
    if (files.length === 0) {
      return;
    }
    const allowedFiles = files.filter(isSupportedAgentAttachment);
    const rejectedCount = files.length - allowedFiles.length;
    if (rejectedCount > 0) {
      setActionError(
        rejectedCount === 1
          ? "Only image and PDF files are supported in agent attachments."
          : `${rejectedCount} files were skipped. Only image and PDF files are supported in agent attachments.`
      );
    } else {
      setActionError(null);
    }
    if (allowedFiles.length === 0) {
      return;
    }

    const nextAttachments = allowedFiles.map((file) => ({
      id: nextDraftAttachmentId(),
      file,
      kind: detectDraftAttachmentKind(file),
      localObjectUrl: URL.createObjectURL(file),
      uploadedAttachmentId: null,
      uploadProgress: 0,
      phase: "uploading" as const,
      errorMessage: null,
      useOcr: attachmentsUseOcr
    }));

    setDraftAttachments((current) => [...current, ...nextAttachments]);
    nextAttachments.forEach((attachment) => startDraftAttachmentUpload(attachment));
  }

  useEffect(() => {
    draftAttachments.forEach((attachment) => {
      if (attachment.useOcr !== attachmentsUseOcr) {
        restartDraftAttachmentUpload(attachment.id, attachmentsUseOcr);
      }
    });
  }, [attachmentsUseOcr, draftAttachments]);

  function handleDraftFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (files.length === 0) {
      return;
    }
    appendDraftAttachments(files);
    event.target.value = "";
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
    const currentAttachment = previousAttachmentsRef.current[attachmentId];
    uploadAbortControllersRef.current[attachmentId]?.abort();
    delete uploadAbortControllersRef.current[attachmentId];
    delete uploadPromisesRef.current[attachmentId];
    setDraftAttachments((current) => current.filter((attachment) => attachment.id !== attachmentId));
    if (currentAttachment?.uploadedAttachmentId) {
      void deleteAgentDraftAttachment(currentAttachment.uploadedAttachmentId).catch((error: Error) => {
        setActionError(error.message);
      });
    }
  }

  function clearAllDraftAttachments() {
    setDraftAttachments((current) => {
      for (const attachment of current) {
        uploadAbortControllersRef.current[attachment.id]?.abort();
        delete uploadAbortControllersRef.current[attachment.id];
        delete uploadPromisesRef.current[attachment.id];
        if (attachment.uploadedAttachmentId) {
          void deleteAgentDraftAttachment(attachment.uploadedAttachmentId).catch((error: Error) => {
            setActionError(error.message);
          });
        }
      }
      return [];
    });
  }

  async function resolveDraftAttachmentsForSend(attachments: DraftAttachment[]): Promise<ReadyDraftAttachment[]> {
    const results = await Promise.all(
      attachments.map(async (attachment) => {
        if (attachment.uploadedAttachmentId) {
          return {
            id: attachment.id,
            file: attachment.file,
            kind: attachment.kind,
            localObjectUrl: attachment.localObjectUrl,
            uploadedAttachmentId: attachment.uploadedAttachmentId
          } satisfies ReadyDraftAttachment;
        }
        const uploadPromise = uploadPromisesRef.current[attachment.id];
        if (!uploadPromise) {
          throw new Error(attachment.errorMessage || `Attachment ${attachment.file.name} is not ready.`);
        }
        return await uploadPromise;
      })
    );
    return results;
  }

  return {
    draftAttachments,
    setDraftAttachments,
    clearAllDraftAttachments,
    isComposerDragActive,
    fileInputRef,
    resolveDraftAttachmentsForSend,
    handlers: {
      handleDraftFileSelection,
      handleComposerPaste,
      handleComposerDragEnter,
      handleComposerDragOver,
      handleComposerDragLeave,
      handleComposerDrop,
      removeDraftAttachment
    }
  };
}

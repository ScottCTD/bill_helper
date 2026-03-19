/**
 * CALLING SPEC:
 * - Purpose: provide the `useAgentDraftAttachments` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/features/agent/panel/useAgentDraftAttachments.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `useAgentDraftAttachments`.
 * - Side effects: client-side state coordination and query wiring.
 */
import {
  type ChangeEvent,
  type ClipboardEvent,
  type DragEvent,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";

import {
  detectDraftAttachmentKind,
  isSupportedAgentAttachment,
  type DraftAttachment,
  type DraftAttachmentPreview
} from "./types";

interface UseAgentDraftAttachmentsArgs {
  setActionError: (message: string | null) => void;
}

export function useAgentDraftAttachments(args: UseAgentDraftAttachmentsArgs) {
  const { setActionError } = args;
  const [draftFiles, setDraftFiles] = useState<DraftAttachment[]>([]);
  const [isComposerDragActive, setIsComposerDragActive] = useState(false);

  const draftFileIdCounterRef = useRef(0);
  const composerDragDepthRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const draftAttachmentPreviews = useMemo<DraftAttachmentPreview[]>(
    () =>
      draftFiles.map((item) => ({
        id: item.id,
        file: item.file,
        url: URL.createObjectURL(item.file),
        kind: detectDraftAttachmentKind(item.file)
      })),
    [draftFiles]
  );

  useEffect(() => {
    return () => {
      draftAttachmentPreviews.forEach((preview) => {
        URL.revokeObjectURL(preview.url);
      });
    };
  }, [draftAttachmentPreviews]);

  function nextDraftAttachmentId(): string {
    draftFileIdCounterRef.current += 1;
    return `draft-attachment-${draftFileIdCounterRef.current}`;
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
    setDraftFiles((current) => [
      ...current,
      ...allowedFiles.map((file) => ({
        id: nextDraftAttachmentId(),
        file
      }))
    ]);
  }

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
    setDraftFiles((current) => current.filter((item) => item.id !== attachmentId));
  }

  return {
    draftFiles,
    setDraftFiles,
    draftAttachmentPreviews,
    isComposerDragActive,
    fileInputRef,
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

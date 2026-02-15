import {
  type ChangeEvent,
  type ClipboardEvent,
  type DragEvent,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";

import { IMAGE_FILENAME_PATTERN, type DraftAttachment, type DraftAttachmentPreview } from "./types";

interface UseAgentDraftAttachmentsArgs {
  setActionError: (message: string | null) => void;
}

export function useAgentDraftAttachments(args: UseAgentDraftAttachmentsArgs) {
  const { setActionError } = args;
  const [draftFiles, setDraftFiles] = useState<DraftAttachment[]>([]);
  const [previewAttachmentId, setPreviewAttachmentId] = useState<string | null>(null);
  const [isComposerDragActive, setIsComposerDragActive] = useState(false);

  const draftFileIdCounterRef = useRef(0);
  const composerDragDepthRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const draftAttachmentPreviews = useMemo<DraftAttachmentPreview[]>(
    () => draftFiles.map((item) => ({ id: item.id, file: item.file, url: URL.createObjectURL(item.file) })),
    [draftFiles]
  );

  useEffect(() => {
    return () => {
      draftAttachmentPreviews.forEach((preview) => {
        URL.revokeObjectURL(preview.url);
      });
    };
  }, [draftAttachmentPreviews]);

  const selectedDraftAttachmentPreview = useMemo(
    () => draftAttachmentPreviews.find((preview) => preview.id === previewAttachmentId) ?? null,
    [draftAttachmentPreviews, previewAttachmentId]
  );

  useEffect(() => {
    if (!previewAttachmentId) {
      return;
    }
    if (selectedDraftAttachmentPreview) {
      return;
    }
    setPreviewAttachmentId(null);
  }, [previewAttachmentId, selectedDraftAttachmentPreview]);

  function nextDraftAttachmentId(): string {
    draftFileIdCounterRef.current += 1;
    return `draft-attachment-${draftFileIdCounterRef.current}`;
  }

  function isImageFile(file: File): boolean {
    const mimeType = file.type.toLowerCase();
    if (mimeType.startsWith("image/")) {
      return true;
    }
    return IMAGE_FILENAME_PATTERN.test(file.name.toLowerCase());
  }

  function appendDraftAttachments(files: File[]): void {
    if (files.length === 0) {
      return;
    }
    const imageFiles = files.filter(isImageFile);
    const rejectedCount = files.length - imageFiles.length;
    if (rejectedCount > 0) {
      setActionError(
        rejectedCount === 1
          ? "Only image files are supported in agent attachments."
          : `${rejectedCount} files were skipped. Only image files are supported in agent attachments.`
      );
    } else {
      setActionError(null);
    }
    if (imageFiles.length === 0) {
      return;
    }
    setDraftFiles((current) => [
      ...current,
      ...imageFiles.map((file) => ({
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
    if (previewAttachmentId === attachmentId) {
      setPreviewAttachmentId(null);
    }
  }

  return {
    draftFiles,
    setDraftFiles,
    draftAttachmentPreviews,
    selectedDraftAttachmentPreview,
    previewAttachmentId,
    setPreviewAttachmentId,
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

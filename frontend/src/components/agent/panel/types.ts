import type { PendingAssistantActivityItem } from "../activity";

export interface DraftAttachment {
  id: string;
  file: File;
}

export type DraftAttachmentKind = "image" | "pdf";

export interface DraftAttachmentPreview {
  id: string;
  file: File;
  url: string;
  kind: DraftAttachmentKind;
}

export interface PendingUserAttachmentPreview {
  id: string;
  name: string;
  url: string;
  mimeType: string;
  kind: DraftAttachmentKind;
}

export interface PendingUserMessage {
  id: string;
  threadId: string;
  content: string;
  createdAt: string;
  baselineLastUserMessageId: string | null;
  attachments: PendingUserAttachmentPreview[];
}

export interface PendingAssistantMessage {
  id: string;
  threadId: string;
  createdAt: string;
  content: string;
  runId: string | null;
  baselineLastAssistantMessageId: string | null;
  activity: PendingAssistantActivityItem[];
}

export const IMAGE_FILENAME_PATTERN = /\.(avif|bmp|gif|heic|heif|jpe?g|png|svg|tiff?|webp)$/i;
export const PDF_FILENAME_PATTERN = /\.pdf$/i;
export const COMPOSER_TEXTAREA_MAX_HEIGHT_PX = 220;

interface AttachmentFileLike {
  name: string;
  type?: string;
}

export function isImageAttachment(file: AttachmentFileLike): boolean {
  const mimeType = (file.type || "").toLowerCase();
  if (mimeType.startsWith("image/")) {
    return true;
  }
  return IMAGE_FILENAME_PATTERN.test(file.name.toLowerCase());
}

export function isPdfAttachment(file: AttachmentFileLike): boolean {
  const mimeType = (file.type || "").toLowerCase();
  if (mimeType === "application/pdf") {
    return true;
  }
  return PDF_FILENAME_PATTERN.test(file.name.toLowerCase());
}

export function isSupportedAgentAttachment(file: AttachmentFileLike): boolean {
  return isImageAttachment(file) || isPdfAttachment(file);
}

export function detectDraftAttachmentKind(file: AttachmentFileLike): DraftAttachmentKind {
  return isPdfAttachment(file) ? "pdf" : "image";
}

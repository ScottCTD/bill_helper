import type { PendingAssistantActivityItem } from "../activity";

export interface DraftAttachment {
  id: string;
  file: File;
}

export interface DraftAttachmentPreview {
  id: string;
  file: File;
  url: string;
}

export interface PendingUserAttachmentPreview {
  id: string;
  name: string;
  url: string;
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
export const COMPOSER_TEXTAREA_MAX_HEIGHT_PX = 220;

/**
 * CALLING SPEC:
 * - Purpose: provide the `helpers` frontend module.
 * - Inputs: callers that import `frontend/src/features/agent/panel/helpers.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `helpers`.
 * - Side effects: module-local frontend behavior only.
 */
import type { AgentThread, AgentThreadSummary, AgentToolCall, RuntimeSettings } from "../../../lib/types";

export const BULK_MODE_HELP_TEXT =
  "Each file starts a fresh thread using only the prompt typed here. Current thread history is not included.";
export const DEFAULT_BULK_LAUNCH_CONCURRENCY_LIMIT = 4;

export function normalizeThreadTitleValue(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized || null;
}

export function extractRenameThreadTitle(toolCall: AgentToolCall): string | null {
  const outputTitle = normalizeThreadTitleValue(toolCall.output_json?.title);
  if (outputTitle) {
    return outputTitle;
  }
  return normalizeThreadTitleValue(toolCall.input_json?.title);
}

export function deriveThreadTitleFromFilename(filename: string): string {
  const stem = filename.replace(/\.[^./\\]+$/, "");
  const normalized = stem.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  const nextTitle = normalized || filename.trim() || "Bulk upload";
  return nextTitle.slice(0, 255);
}

export function normalizeModelName(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim();
  return normalized || null;
}

export function resolveComposerModelName(
  availableModels: string[],
  threadDetail?: { runs: { model_name: string | null }[]; configured_model_name: string | null },
  runtimeSettings?: RuntimeSettings
): string {
  const latestRunModelName = normalizeModelName(threadDetail?.runs.at(-1)?.model_name);
  const configuredModelName = normalizeModelName(threadDetail?.configured_model_name);
  const runtimeDefaultModelName = normalizeModelName(runtimeSettings?.agent_model);
  const fallbackModelName = normalizeModelName(availableModels[0]);

  if (availableModels.length === 0) {
    return "";
  }

  for (const candidate of [latestRunModelName, configuredModelName, runtimeDefaultModelName, fallbackModelName]) {
    if (candidate && availableModels.includes(candidate)) {
      return candidate;
    }
  }

  return fallbackModelName ?? "";
}

export function buildThreadSummary(
  thread: AgentThread,
  overrides: Partial<AgentThreadSummary> = {}
): AgentThreadSummary {
  return {
    ...thread,
    last_message_preview: null,
    pending_change_count: 0,
    has_running_run: false,
    ...overrides
  };
}

export function summarizeFilenames(fileNames: string[]): string {
  if (fileNames.length <= 3) {
    return fileNames.join(", ");
  }
  return `${fileNames.slice(0, 3).join(", ")}, and ${fileNames.length - 3} more`;
}

export async function mapWithConcurrency<T, R>(
  items: readonly T[],
  concurrency: number,
  iteratee: (item: T, index: number) => Promise<R>
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let nextIndex = 0;

  async function worker() {
    while (nextIndex < items.length) {
      const currentIndex = nextIndex;
      nextIndex += 1;
      results[currentIndex] = await iteratee(items[currentIndex], currentIndex);
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, () => worker()));
  return results;
}

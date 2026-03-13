/**
 * CALLING SPEC:
 * - Purpose: provide the `constants` frontend module.
 * - Inputs: callers that import `frontend/src/features/settings/constants.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `constants`.
 * - Side effects: module-local frontend behavior only.
 */
import type { SettingsTabDefinition } from "./types";

export const SETTINGS_FIELD_IDS = {
  agentMemory: "settings-agent-memory",
  defaultModel: "settings-default-model",
  defaultTaggingModel: "settings-default-tagging-model",
  availableModels: "settings-available-models",
  bulkMaxThreads: "settings-bulk-max-threads",
  maxAttachmentsPerMessage: "settings-max-attachments-per-message",
} as const;

export const SETTINGS_TABS: SettingsTabDefinition[] = [
  {
    id: "general",
    label: "General",
    description: "Identity context and workspace defaults used by entries and dashboard views.",
  },
  {
    id: "agent",
    label: "Agent",
    description: "Model selection, provider overrides, bulk limits, attachment guardrails, and reliability settings.",
  },
];

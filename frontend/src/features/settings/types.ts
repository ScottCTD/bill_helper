/**
 * CALLING SPEC:
 * - Purpose: provide the `types` frontend module.
 * - Inputs: callers that import `frontend/src/features/settings/types.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `types`.
 * - Side effects: module-local frontend behavior only.
 */
export interface SettingsFormState {
  user_memory: string;
  default_currency_code: string;
  dashboard_currency_code: string;
  agent_model: string;
  entry_tagging_model: string;
  available_agent_models: string;
  agent_model_display_names: Record<string, string>;
  agent_max_steps: string;
  agent_bulk_max_concurrent_threads: string;
  agent_max_images_per_message: string;
  agent_max_image_size_mb: string;
  agent_retry_max_attempts: string;
  agent_retry_initial_wait_seconds: string;
  agent_retry_max_wait_seconds: string;
  agent_retry_backoff_multiplier: string;
  agent_base_url: string;
  agent_api_key: string;
  use_custom_provider_override: boolean;
  agent_api_key_configured: boolean;
  agent_api_key_dirty: boolean;
}

export type SettingsTab = "general" | "agent";

export interface SettingsTabDefinition {
  id: SettingsTab;
  label: string;
  description: string;
}

export type SettingsFormPatch = Partial<SettingsFormState>;

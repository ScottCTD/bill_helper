/**
 * CALLING SPEC:
 * - Purpose: define runtime settings contracts for the frontend.
 * - Inputs: frontend modules that read or update runtime settings.
 * - Outputs: runtime settings interfaces and patch payloads.
 * - Side effects: type declarations only.
 */

export interface RuntimeSettingsOverrides {
  user_memory: string[] | null;
  default_currency_code: string | null;
  dashboard_currency_code: string | null;
  agent_model: string | null;
  entry_tagging_model: string | null;
  available_agent_models: string[] | null;
  agent_model_display_names: Record<string, string> | null;
  agent_max_steps: number | null;
  agent_bulk_max_concurrent_threads: number | null;
  agent_retry_max_attempts: number | null;
  agent_retry_initial_wait_seconds: number | null;
  agent_retry_max_wait_seconds: number | null;
  agent_retry_backoff_multiplier: number | null;
  agent_max_image_size_bytes: number | null;
  agent_max_images_per_message: number | null;
  agent_base_url: string | null;
  agent_api_key_configured: boolean;
}

export interface RuntimeSettings {
  user_memory: string[] | null;
  default_currency_code: string;
  dashboard_currency_code: string;
  agent_model: string;
  entry_tagging_model: string | null;
  available_agent_models: string[];
  agent_model_display_names: Record<string, string>;
  vision_capable_agent_models?: string[];
  agent_max_steps: number;
  agent_bulk_max_concurrent_threads: number;
  agent_retry_max_attempts: number;
  agent_retry_initial_wait_seconds: number;
  agent_retry_max_wait_seconds: number;
  agent_retry_backoff_multiplier: number;
  agent_max_image_size_bytes: number;
  agent_max_images_per_message: number;
  agent_base_url: string | null;
  agent_api_key_configured: boolean;
  overrides: RuntimeSettingsOverrides;
}

export interface RuntimeSettingsUpdatePayload {
  user_memory?: string[] | null;
  default_currency_code?: string | null;
  dashboard_currency_code?: string | null;
  agent_model?: string | null;
  entry_tagging_model?: string | null;
  available_agent_models?: string[] | null;
  agent_model_display_names?: Record<string, string> | null;
  agent_max_steps?: number | null;
  agent_bulk_max_concurrent_threads?: number | null;
  agent_retry_max_attempts?: number | null;
  agent_retry_initial_wait_seconds?: number | null;
  agent_retry_max_wait_seconds?: number | null;
  agent_retry_backoff_multiplier?: number | null;
  agent_max_image_size_bytes?: number | null;
  agent_max_images_per_message?: number | null;
  agent_base_url?: string | null;
  agent_api_key?: string | null;
}

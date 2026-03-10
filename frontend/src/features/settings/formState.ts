import type { RuntimeSettings, RuntimeSettingsUpdatePayload } from "../../lib/types";
import type { SettingsFormState } from "./types";

const USER_MEMORY_LINE_PREFIXES = ["- ", "* ", "+ "];

export const RESET_RUNTIME_SETTINGS_PAYLOAD: RuntimeSettingsUpdatePayload = {
  user_memory: null,
  default_currency_code: null,
  dashboard_currency_code: null,
  agent_model: null,
  available_agent_models: [],
  agent_max_steps: null,
  agent_bulk_max_concurrent_threads: null,
  agent_max_images_per_message: null,
  agent_max_image_size_bytes: null,
  agent_retry_max_attempts: null,
  agent_retry_initial_wait_seconds: null,
  agent_retry_max_wait_seconds: null,
  agent_retry_backoff_multiplier: null,
  agent_base_url: null,
  agent_api_key: null,
};

function bytesToMegabytes(value: number): string {
  const mb = value / (1024 * 1024);
  return Number.isInteger(mb) ? mb.toString() : mb.toFixed(2);
}

function hasStoredProviderOverride(data: RuntimeSettings): boolean {
  return data.overrides.agent_base_url !== null || data.overrides.agent_api_key_configured;
}

function formatLines(items: string[] | null): string {
  return (items ?? []).join("\n");
}

function normalizeUserMemoryLine(rawValue: string): string | null {
  let normalized = rawValue.trim();
  if (!normalized) {
    return null;
  }
  for (const prefix of USER_MEMORY_LINE_PREFIXES) {
    if (normalized.startsWith(prefix)) {
      normalized = normalized.slice(prefix.length).trim();
      break;
    }
  }
  return normalized || null;
}

function parseUserMemoryLines(rawValue: string): string[] | null {
  const items: string[] = [];
  const seenKeys = new Set<string>();

  for (const line of rawValue.split(/\r?\n/)) {
    const item = normalizeUserMemoryLine(line);
    if (!item) {
      continue;
    }
    const itemKey = item.toLocaleLowerCase();
    if (seenKeys.has(itemKey)) {
      continue;
    }
    seenKeys.add(itemKey);
    items.push(item);
  }

  return items.length > 0 ? items : null;
}

function parseAgentModelLines(rawValue: string): string[] {
  const items: string[] = [];
  const seenKeys = new Set<string>();

  for (const line of rawValue.split(/\r?\n/)) {
    const item = line.trim();
    if (!item) {
      continue;
    }
    const itemKey = item.toLocaleLowerCase();
    if (seenKeys.has(itemKey)) {
      continue;
    }
    seenKeys.add(itemKey);
    items.push(item);
  }

  return items;
}

function parsePositiveInteger(rawValue: string, fieldName: string): number {
  const parsed = Number(rawValue);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${fieldName} must be a positive integer.`);
  }
  return parsed;
}

function parseNonNegativeNumber(rawValue: string, fieldName: string): number {
  const parsed = Number(rawValue);
  if (!Number.isFinite(parsed) || parsed < 0) {
    throw new Error(`${fieldName} must be a non-negative number.`);
  }
  return parsed;
}

export function buildSettingsFormState(data: RuntimeSettings): SettingsFormState {
  return {
    current_user_name: data.current_user_name,
    user_memory: formatLines(data.user_memory),
    default_currency_code: data.default_currency_code,
    dashboard_currency_code: data.dashboard_currency_code,
    agent_model: data.agent_model,
    available_agent_models: formatLines(data.available_agent_models),
    agent_max_steps: String(data.agent_max_steps),
    agent_bulk_max_concurrent_threads: String(data.agent_bulk_max_concurrent_threads),
    agent_max_images_per_message: String(data.agent_max_images_per_message),
    agent_max_image_size_mb: bytesToMegabytes(data.agent_max_image_size_bytes),
    agent_retry_max_attempts: String(data.agent_retry_max_attempts),
    agent_retry_initial_wait_seconds: String(data.agent_retry_initial_wait_seconds),
    agent_retry_max_wait_seconds: String(data.agent_retry_max_wait_seconds),
    agent_retry_backoff_multiplier: String(data.agent_retry_backoff_multiplier),
    agent_base_url: data.agent_base_url ?? "",
    agent_api_key: "",
    use_custom_provider_override: hasStoredProviderOverride(data),
    agent_api_key_configured: data.agent_api_key_configured ?? false,
    agent_api_key_dirty: false,
  };
}

export function buildSettingsUpdatePayload(formState: SettingsFormState): RuntimeSettingsUpdatePayload {
  const nextDefaultCurrencyCode = formState.default_currency_code.trim().toUpperCase();
  const nextDashboardCurrencyCode = formState.dashboard_currency_code.trim().toUpperCase();
  if (nextDefaultCurrencyCode.length !== 3 || nextDashboardCurrencyCode.length !== 3) {
    throw new Error("Currency codes must use 3-letter ISO codes.");
  }

  const nextAgentMaxSteps = parsePositiveInteger(formState.agent_max_steps, "Agent max steps");
  const nextAgentBulkMaxConcurrentThreads = parsePositiveInteger(
    formState.agent_bulk_max_concurrent_threads,
    "Bulk mode max concurrent threads"
  );
  if (nextAgentBulkMaxConcurrentThreads > 16) {
    throw new Error("Bulk mode max concurrent threads must be 16 or less.");
  }

  const nextAgentMaxImagesPerMessage = parsePositiveInteger(
    formState.agent_max_images_per_message,
    "Max attachments per message"
  );
  const nextAgentRetryMaxAttempts = parsePositiveInteger(formState.agent_retry_max_attempts, "Retry max attempts");
  const nextAgentRetryInitialWaitSeconds = parseNonNegativeNumber(
    formState.agent_retry_initial_wait_seconds,
    "Retry initial wait"
  );
  const nextAgentRetryMaxWaitSeconds = parseNonNegativeNumber(formState.agent_retry_max_wait_seconds, "Retry max wait");
  const nextAgentRetryBackoffMultiplier = parseNonNegativeNumber(
    formState.agent_retry_backoff_multiplier,
    "Retry backoff multiplier"
  );
  if (nextAgentRetryBackoffMultiplier < 1) {
    throw new Error("Retry backoff multiplier must be at least 1.");
  }

  const imageSizeMb = parseNonNegativeNumber(formState.agent_max_image_size_mb, "Attachment size limit");
  if (imageSizeMb <= 0) {
    throw new Error("Attachment size limit must be greater than 0.");
  }
  const nextAgentMaxImageSizeBytes = Math.round(imageSizeMb * 1024 * 1024);

  const nextAgentBaseUrl = formState.use_custom_provider_override ? formState.agent_base_url.trim() || null : null;
  const nextAgentApiKey = formState.use_custom_provider_override
    ? formState.agent_api_key_dirty
      ? formState.agent_api_key.trim() || null
      : undefined
    : null;

  const payload: RuntimeSettingsUpdatePayload = {
    user_memory: parseUserMemoryLines(formState.user_memory),
    default_currency_code: nextDefaultCurrencyCode,
    dashboard_currency_code: nextDashboardCurrencyCode,
    agent_model: formState.agent_model.trim(),
    available_agent_models: parseAgentModelLines(formState.available_agent_models),
    agent_max_steps: nextAgentMaxSteps,
    agent_bulk_max_concurrent_threads: nextAgentBulkMaxConcurrentThreads,
    agent_max_images_per_message: nextAgentMaxImagesPerMessage,
    agent_max_image_size_bytes: nextAgentMaxImageSizeBytes,
    agent_retry_max_attempts: nextAgentRetryMaxAttempts,
    agent_retry_initial_wait_seconds: nextAgentRetryInitialWaitSeconds,
    agent_retry_max_wait_seconds: nextAgentRetryMaxWaitSeconds,
    agent_retry_backoff_multiplier: nextAgentRetryBackoffMultiplier,
    agent_base_url: nextAgentBaseUrl,
  };

  if (nextAgentApiKey !== undefined) {
    payload.agent_api_key = nextAgentApiKey;
  }

  return payload;
}

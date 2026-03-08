import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { FormField } from "../components/ui/form-field";
import { Input } from "../components/ui/input";
import { Switch } from "../components/ui/switch";
import { NativeSelect } from "../components/ui/native-select";
import { Textarea } from "../components/ui/textarea";
import { getRuntimeSettings, listCurrencies, updateRuntimeSettings } from "../lib/api";
import { invalidateRuntimeSettingsReadModels } from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";
import type { RuntimeSettings, RuntimeSettingsUpdatePayload } from "../lib/types";

interface SettingsFormState {
  current_user_name: string;
  user_memory: string;
  default_currency_code: string;
  dashboard_currency_code: string;
  agent_model: string;
  available_agent_models: string;
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

const USER_MEMORY_LINE_PREFIXES = ["- ", "* ", "+ "];

function bytesToMegabytes(value: number): string {
  const mb = value / (1024 * 1024);
  const rounded = Number.isInteger(mb) ? mb.toString() : mb.toFixed(2);
  return rounded;
}

function hasStoredProviderOverride(data: RuntimeSettings): boolean {
  return data.overrides.agent_base_url !== null || data.overrides.agent_api_key_configured;
}

function formatUserMemoryLines(items: string[] | null): string {
  return (items ?? []).join("\n");
}

function formatAgentModelLines(items: string[] | null): string {
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

function normalizeAgentModelLine(rawValue: string): string | null {
  const normalized = rawValue.trim();
  return normalized || null;
}

function parseAgentModelLines(rawValue: string): string[] {
  const items: string[] = [];
  const seenKeys = new Set<string>();
  for (const line of rawValue.split(/\r?\n/)) {
    const item = normalizeAgentModelLine(line);
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

function buildFormState(data: RuntimeSettings): SettingsFormState {
  return {
    current_user_name: data.current_user_name,
    user_memory: formatUserMemoryLines(data.user_memory),
    default_currency_code: data.default_currency_code,
    dashboard_currency_code: data.dashboard_currency_code,
    agent_model: data.agent_model,
    available_agent_models: formatAgentModelLines(data.available_agent_models),
    agent_max_steps: String(data.agent_max_steps),
    agent_bulk_max_concurrent_threads: String(data.agent_bulk_max_concurrent_threads),
    agent_max_images_per_message: String(data.agent_max_images_per_message),
    agent_max_image_size_mb: bytesToMegabytes(data.agent_max_image_size_bytes),
    agent_retry_max_attempts: String(data.agent_retry_max_attempts),
    agent_retry_initial_wait_seconds: String(data.agent_retry_initial_wait_seconds),
    agent_retry_max_wait_seconds: String(data.agent_retry_max_wait_seconds),
    agent_retry_backoff_multiplier: String(data.agent_retry_backoff_multiplier),
    agent_base_url: data.agent_base_url ?? "",
    agent_api_key: "", // Always empty - user must re-enter to change
    use_custom_provider_override: hasStoredProviderOverride(data),
    agent_api_key_configured: data.agent_api_key_configured ?? false,
    agent_api_key_dirty: false,
  };
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

export function SettingsPage() {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: queryKeys.settings.runtime,
    queryFn: getRuntimeSettings,
  });
  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });

  const [formState, setFormState] = useState<SettingsFormState | null>(null);
  const [initialState, setInitialState] = useState<SettingsFormState | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const updateMutation = useMutation({
    mutationFn: updateRuntimeSettings,
    onSuccess: () => {
      invalidateRuntimeSettingsReadModels(queryClient);
      setFormError(null);
    },
    onError: (error) => {
      setFormError((error as Error).message);
    },
  });

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }
    const nextFormState = buildFormState(settingsQuery.data);
    setFormState(nextFormState);
    setInitialState(nextFormState);
    setFormError(null);
  }, [settingsQuery.data]);

  const currencyOptions = useMemo(() => {
    const codes = new Set((currenciesQuery.data ?? []).map((currency) => currency.code));
    if (formState?.default_currency_code) {
      codes.add(formState.default_currency_code.toUpperCase());
    }
    if (formState?.dashboard_currency_code) {
      codes.add(formState.dashboard_currency_code.toUpperCase());
    }
    return Array.from(codes).sort();
  }, [currenciesQuery.data, formState?.dashboard_currency_code, formState?.default_currency_code]);

  const isDirty = useMemo(() => {
    if (!formState || !initialState) {
      return false;
    }
    return JSON.stringify(formState) !== JSON.stringify(initialState);
  }, [formState, initialState]);

  function submitSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!formState) {
      return;
    }
    setFormError(null);
    try {
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
      const nextAgentRetryMaxAttempts = parsePositiveInteger(
        formState.agent_retry_max_attempts,
        "Retry max attempts"
      );
      const nextAgentRetryInitialWaitSeconds = parseNonNegativeNumber(
        formState.agent_retry_initial_wait_seconds,
        "Retry initial wait"
      );
      const nextAgentRetryMaxWaitSeconds = parseNonNegativeNumber(
        formState.agent_retry_max_wait_seconds,
        "Retry max wait"
      );
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

      const nextAgentBaseUrl = formState.use_custom_provider_override
        ? (formState.agent_base_url.trim() || null)
        : null;
      const nextAgentApiKey = formState.use_custom_provider_override
        ? (formState.agent_api_key_dirty ? (formState.agent_api_key.trim() || null) : undefined)
        : null;
      const nextAgentModel = formState.agent_model.trim();
      const nextAvailableAgentModels = parseAgentModelLines(formState.available_agent_models);
      const nextUserMemory = parseUserMemoryLines(formState.user_memory);

      const payload: RuntimeSettingsUpdatePayload = {
        user_memory: nextUserMemory,
        default_currency_code: nextDefaultCurrencyCode,
        dashboard_currency_code: nextDashboardCurrencyCode,
        agent_model: nextAgentModel,
        available_agent_models: nextAvailableAgentModels,
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

      // Only include agent_api_key if it was explicitly changed while custom override is enabled,
      // or always clear it when the override toggle is disabled.
      if (nextAgentApiKey !== undefined) {
        payload.agent_api_key = nextAgentApiKey;
      }

      updateMutation.mutate(payload);
    } catch (error) {
      setFormError((error as Error).message);
    }
  }

  function resetOverrides() {
    updateMutation.mutate({
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
    });
  }

  if (settingsQuery.isLoading && !formState) {
    return <p>Loading settings...</p>;
  }

  if (settingsQuery.isError && !formState) {
    return <p className="error">Failed to load settings: {(settingsQuery.error as Error).message}</p>;
  }

  if (!formState || !settingsQuery.data) {
    return null;
  }

  return (
    <div className="stack-lg">
      <Card className="overflow-hidden">
        <CardHeader className="relative gap-4 pb-4">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-muted/55 via-background to-secondary/45" />
          <div className="relative flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Settings</CardTitle>
              <CardDescription>Configure defaults for entries, dashboard analytics, and agent runtime behavior.</CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">Default model: {settingsQuery.data.agent_model}</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="relative flex flex-wrap items-center gap-2">
          <Button form="runtime-settings-form" type="submit" disabled={!isDirty || updateMutation.isPending}>
            {updateMutation.isPending ? "Saving..." : "Save changes"}
          </Button>
          <Button type="button" variant="outline" onClick={resetOverrides} disabled={updateMutation.isPending}>
            Reset to server defaults
          </Button>
          {formError ? <p className="error w-full">{formError}</p> : null}
        </CardContent>
      </Card>

      <form id="runtime-settings-form" className="grid gap-4 xl:grid-cols-2" onSubmit={submitSettings}>
        <Card>
          <CardHeader>
            <CardTitle>General</CardTitle>
            <CardDescription>Defaults used by new ledger flows. Request identity is controlled by the active principal, not settings.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <FormField
              label="Current user name"
              hint="Read-only request principal for this session."
            >
              <Input value={formState.current_user_name} readOnly />
            </FormField>

            <FormField label="Default currency" hint="Used when entry currency is omitted in agent proposals and entry defaults.">
              <NativeSelect
                value={formState.default_currency_code}
                onChange={(event) =>
                  setFormState((state) => (state ? { ...state, default_currency_code: event.target.value.toUpperCase() } : state))
                }
              >
                {currencyOptions.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </NativeSelect>
            </FormField>

            <FormField label="Dashboard currency" hint="Used by dashboard analytics and reconciliation views.">
              <NativeSelect
                value={formState.dashboard_currency_code}
                onChange={(event) =>
                  setFormState((state) => (state ? { ...state, dashboard_currency_code: event.target.value.toUpperCase() } : state))
                }
              >
                {currencyOptions.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </NativeSelect>
            </FormField>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Agent Runtime</CardTitle>
            <CardDescription>Controls model selection and guardrails for new runs and bulk launches.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <FormField
              label="Agent memory"
              hint="Persistent agent memory added to every system prompt. Enter one preference/rule/hint per line."
            >
              <Textarea
                value={formState.user_memory}
                onChange={(event) => setFormState((state) => (state ? { ...state, user_memory: event.target.value } : state))}
              />
            </FormField>

            <FormField
              label="Default model"
              hint="Used for new chats and runs. If it is missing from Available models, the server adds it to the effective list."
            >
              <Input
                value={formState.agent_model}
                onChange={(event) => setFormState((state) => (state ? { ...state, agent_model: event.target.value } : state))}
              />
            </FormField>

            <FormField
              label="Available models"
              hint="Enter one model identifier per line. Blank lines are ignored and order is preserved."
            >
              <Textarea
                value={formState.available_agent_models}
                onChange={(event) =>
                  setFormState((state) => (state ? { ...state, available_agent_models: event.target.value } : state))
                }
              />
            </FormField>

            <div className="flex items-start justify-between gap-4 rounded-xl border border-border/70 bg-muted/20 px-4 py-3">
              <div className="grid gap-1">
                <p className="text-sm font-medium text-foreground">Custom provider override</p>
                <p className="text-xs text-muted-foreground">
                  Off uses server env. On stores a custom endpoint and API key in runtime settings.
                </p>
              </div>
              <Switch
                aria-label="Use custom provider override"
                checked={formState.use_custom_provider_override}
                onCheckedChange={(checked) =>
                  setFormState((state) =>
                    state
                      ? {
                          ...state,
                          use_custom_provider_override: checked,
                        }
                      : state
                  )
                }
              />
            </div>

            {formState.use_custom_provider_override ? (
              <>
                <FormField
                  label="Custom API endpoint"
                  hint="Optional custom base URL for the model provider."
                >
                  <Input
                    aria-label="Custom API endpoint"
                    type="url"
                    placeholder="https://api.example.com/v1"
                    value={formState.agent_base_url}
                    onChange={(event) => setFormState((state) => (state ? { ...state, agent_base_url: event.target.value } : state))}
                  />
                </FormField>

                <FormField
                  label="Custom API key"
                  hint={
                    formState.agent_api_key_configured
                      ? "A stored API key exists. Enter a new value to replace it, or leave this empty to keep it."
                      : "API key for the custom provider."
                  }
                >
                  <Input
                    aria-label="Custom API key"
                    type="password"
                    placeholder={formState.agent_api_key_configured ? "••••••••" : "Enter API key"}
                    value={formState.agent_api_key}
                    onChange={(event) =>
                      setFormState((state) => (state ? { ...state, agent_api_key: event.target.value, agent_api_key_dirty: true } : state))
                    }
                  />
                </FormField>
              </>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-3">
              <FormField label="Max steps">
                <Input
                  type="number"
                  min={1}
                  value={formState.agent_max_steps}
                  onChange={(event) => setFormState((state) => (state ? { ...state, agent_max_steps: event.target.value } : state))}
                />
              </FormField>
              <FormField label="Bulk max threads" hint="Maximum fresh threads Bulk mode starts at once.">
                <Input
                  type="number"
                  min={1}
                  max={16}
                  value={formState.agent_bulk_max_concurrent_threads}
                  onChange={(event) =>
                    setFormState((state) =>
                      state ? { ...state, agent_bulk_max_concurrent_threads: event.target.value } : state
                    )
                  }
                />
              </FormField>
              <FormField label="Max attachments per message">
                <Input
                  type="number"
                  min={1}
                  value={formState.agent_max_images_per_message}
                  onChange={(event) =>
                    setFormState((state) => (state ? { ...state, agent_max_images_per_message: event.target.value } : state))
                  }
                />
              </FormField>
            </div>

            <FormField label="Max attachment size (MB)">
              <Input
                type="number"
                min={0.1}
                step={0.1}
                value={formState.agent_max_image_size_mb}
                onChange={(event) =>
                  setFormState((state) => (state ? { ...state, agent_max_image_size_mb: event.target.value } : state))
                }
              />
            </FormField>
          </CardContent>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Reliability</CardTitle>
            <CardDescription>Retry settings for model and tool-call orchestration.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <FormField label="Retry max attempts">
              <Input
                type="number"
                min={1}
                value={formState.agent_retry_max_attempts}
                onChange={(event) =>
                  setFormState((state) => (state ? { ...state, agent_retry_max_attempts: event.target.value } : state))
                }
              />
            </FormField>
            <FormField label="Retry initial wait (s)">
              <Input
                type="number"
                min={0}
                step={0.05}
                value={formState.agent_retry_initial_wait_seconds}
                onChange={(event) =>
                  setFormState((state) => (state ? { ...state, agent_retry_initial_wait_seconds: event.target.value } : state))
                }
              />
            </FormField>
            <FormField label="Retry max wait (s)">
              <Input
                type="number"
                min={0}
                step={0.1}
                value={formState.agent_retry_max_wait_seconds}
                onChange={(event) =>
                  setFormState((state) => (state ? { ...state, agent_retry_max_wait_seconds: event.target.value } : state))
                }
              />
            </FormField>
            <FormField label="Backoff multiplier">
              <Input
                type="number"
                min={1}
                step={0.1}
                value={formState.agent_retry_backoff_multiplier}
                onChange={(event) =>
                  setFormState((state) => (state ? { ...state, agent_retry_backoff_multiplier: event.target.value } : state))
                }
              />
            </FormField>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}

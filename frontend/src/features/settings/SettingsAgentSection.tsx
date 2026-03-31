/**
 * CALLING SPEC:
 * - Purpose: render the `SettingsAgentSection` React UI module.
 * - Inputs: callers that import `frontend/src/features/settings/SettingsAgentSection.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `SettingsAgentSection`.
 * - Side effects: React rendering and user event wiring.
 */
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { FormField } from "../../components/ui/form-field";
import { Input } from "../../components/ui/input";
import { NativeSelect } from "../../components/ui/native-select";
import { Switch } from "../../components/ui/switch";
import { Textarea } from "../../components/ui/textarea";
import { resolveAgentModelOptionLabel } from "../../lib/agent_models";
import { AgentAvailableModelsEditor } from "./AgentAvailableModelsEditor";
import { SETTINGS_FIELD_IDS } from "./constants";
import { parseAgentModelLines } from "./formState";
import type { SettingsFormPatch, SettingsFormState } from "./types";

interface SettingsAgentSectionProps {
  formState: SettingsFormState;
  onFormPatch: (patch: SettingsFormPatch) => void;
}

interface SettingsFormPatchHandlerProps {
  formState: SettingsFormState;
  onFormPatch: (patch: SettingsFormPatch) => void;
}

function MemoryAndModelsCard({ formState, onFormPatch }: SettingsFormPatchHandlerProps) {
  const availableModelOptions = parseAgentModelLines(formState.available_agent_models);
  const hasAvailableModels = availableModelOptions.length > 0;
  const defaultModelValue = hasAvailableModels
    ? availableModelOptions.includes(formState.agent_model)
      ? formState.agent_model
      : availableModelOptions[0]
    : "";
  const taggingModelValue =
    hasAvailableModels && availableModelOptions.includes(formState.entry_tagging_model) ? formState.entry_tagging_model : "";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Memory and models</CardTitle>
        <CardDescription>Persistent prompt memory and model availability for new agent runs.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <FormField
          label="Agent memory"
          htmlFor={SETTINGS_FIELD_IDS.agentMemory}
          hint="Persistent agent memory added to every system prompt. Enter one preference, rule, or hint per line."
        >
          <Textarea
            id={SETTINGS_FIELD_IDS.agentMemory}
            value={formState.user_memory}
            onChange={(event) => onFormPatch({ user_memory: event.target.value })}
          />
        </FormField>

        <FormField
          label="Available models"
          htmlFor={SETTINGS_FIELD_IDS.availableModels}
          hint="Add one row per model: LiteLLM model id and optional display label. Order is preserved; duplicate ids (ignoring case) are dropped when saving. Default model and tagging model below use these ids and labels."
        >
          <AgentAvailableModelsEditor formState={formState} onFormPatch={onFormPatch} fieldId={SETTINGS_FIELD_IDS.availableModels} />
        </FormField>

        <FormField
          label="Default model"
          htmlFor={SETTINGS_FIELD_IDS.defaultModel}
          hint="Used for new chats and runs. Values match the available models list above; option text uses display labels when set."
        >
          <NativeSelect
            id={SETTINGS_FIELD_IDS.defaultModel}
            value={defaultModelValue}
            disabled={!hasAvailableModels}
            onChange={(event) => onFormPatch({ agent_model: event.target.value })}
          >
            {!hasAvailableModels ? <option value="">No available models configured</option> : null}
            {availableModelOptions.map((modelName) => (
              <option key={modelName} value={modelName}>
                {resolveAgentModelOptionLabel(modelName, formState.agent_model_display_names)}
              </option>
            ))}
          </NativeSelect>
        </FormField>

        <FormField
          label="Default tagging model"
          htmlFor={SETTINGS_FIELD_IDS.defaultTaggingModel}
          hint="Used only for inline entry tag suggestions. Leave blank to disable the feature. Option text uses display labels when set."
        >
          <NativeSelect
            id={SETTINGS_FIELD_IDS.defaultTaggingModel}
            value={taggingModelValue}
            onChange={(event) => onFormPatch({ entry_tagging_model: event.target.value })}
          >
            <option value="">Disabled</option>
            {availableModelOptions.map((modelName) => (
              <option key={modelName} value={modelName}>
                {resolveAgentModelOptionLabel(modelName, formState.agent_model_display_names)}
              </option>
            ))}
          </NativeSelect>
        </FormField>
      </CardContent>
    </Card>
  );
}

function ProviderOverrideCard({ formState, onFormPatch }: SettingsFormPatchHandlerProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Provider override</CardTitle>
        <CardDescription>Optional endpoint and API key override stored in runtime settings instead of server env.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="flex items-start justify-between gap-4 rounded-xl border border-border/70 bg-muted/20 px-4 py-3">
          <div className="grid gap-1">
            <p className="text-sm font-medium text-foreground">Use custom provider override</p>
            <p className="text-xs text-muted-foreground">
              Off uses server env. On stores a custom endpoint and API key in runtime settings.
            </p>
          </div>
          <Switch
            aria-label="Use custom provider override"
            checked={formState.use_custom_provider_override}
            onCheckedChange={(checked) => onFormPatch({ use_custom_provider_override: checked })}
          />
        </div>

        {formState.use_custom_provider_override ? (
          <>
            <FormField label="Custom API endpoint" hint="Optional custom base URL for the model provider.">
              <Input
                aria-label="Custom API endpoint"
                type="url"
                placeholder="https://api.example.com/v1"
                value={formState.agent_base_url}
                onChange={(event) => onFormPatch({ agent_base_url: event.target.value })}
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
                  onFormPatch({
                    agent_api_key: event.target.value,
                    agent_api_key_dirty: true,
                  })
                }
              />
            </FormField>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

function RunLimitsCard({ formState, onFormPatch }: SettingsFormPatchHandlerProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Run limits</CardTitle>
        <CardDescription>General limits that apply to individual agent runs.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <FormField label="Max steps" hint="Maximum model-tool orchestration steps allowed in one run.">
          <Input
            type="number"
            min={1}
            value={formState.agent_max_steps}
            onChange={(event) => onFormPatch({ agent_max_steps: event.target.value })}
          />
        </FormField>
      </CardContent>
    </Card>
  );
}

function BulkAndAttachmentsCard({ formState, onFormPatch }: SettingsFormPatchHandlerProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Bulk mode and attachments</CardTitle>
        <CardDescription>Controls bulk launch concurrency and per-message attachment guardrails.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            label="Bulk concurrent launches"
            htmlFor={SETTINGS_FIELD_IDS.bulkMaxThreads}
            hint="How many Bulk mode threads can start at once. Extra attachments wait until one launch request returns."
          >
            <Input
              id={SETTINGS_FIELD_IDS.bulkMaxThreads}
              type="number"
              min={1}
              max={16}
              value={formState.agent_bulk_max_concurrent_threads}
              onChange={(event) => onFormPatch({ agent_bulk_max_concurrent_threads: event.target.value })}
            />
          </FormField>

          <FormField
            label="Max attachments per single message"
            htmlFor={SETTINGS_FIELD_IDS.maxAttachmentsPerMessage}
            hint="Applies to one normal message send. Bulk mode still starts one fresh thread per attachment."
          >
            <Input
              id={SETTINGS_FIELD_IDS.maxAttachmentsPerMessage}
              type="number"
              min={1}
              value={formState.agent_max_images_per_message}
              onChange={(event) => onFormPatch({ agent_max_images_per_message: event.target.value })}
            />
          </FormField>
        </div>

        <FormField label="Max attachment size (MB)" hint="Per-file upload size limit for image and PDF attachments.">
          <Input
            type="number"
            min={0.1}
            step={0.1}
            value={formState.agent_max_image_size_mb}
            onChange={(event) => onFormPatch({ agent_max_image_size_mb: event.target.value })}
          />
        </FormField>
      </CardContent>
    </Card>
  );
}

function ReliabilityCard({ formState, onFormPatch }: SettingsFormPatchHandlerProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Reliability</CardTitle>
        <CardDescription>Retry settings for model and tool-call orchestration.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Retry max attempts">
            <Input
              type="number"
              min={1}
              value={formState.agent_retry_max_attempts}
              onChange={(event) => onFormPatch({ agent_retry_max_attempts: event.target.value })}
            />
          </FormField>

          <FormField label="Backoff multiplier">
            <Input
              type="number"
              min={1}
              step={0.1}
              value={formState.agent_retry_backoff_multiplier}
              onChange={(event) => onFormPatch({ agent_retry_backoff_multiplier: event.target.value })}
            />
          </FormField>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Retry initial wait (s)">
            <Input
              type="number"
              min={0}
              step={0.05}
              value={formState.agent_retry_initial_wait_seconds}
              onChange={(event) => onFormPatch({ agent_retry_initial_wait_seconds: event.target.value })}
            />
          </FormField>

          <FormField label="Retry max wait (s)">
            <Input
              type="number"
              min={0}
              step={0.1}
              value={formState.agent_retry_max_wait_seconds}
              onChange={(event) => onFormPatch({ agent_retry_max_wait_seconds: event.target.value })}
            />
          </FormField>
        </div>
      </CardContent>
    </Card>
  );
}

export function SettingsAgentSection({ formState, onFormPatch }: SettingsAgentSectionProps) {
  return (
    <div id="settings-panel-agent" role="tabpanel" aria-labelledby="settings-tab-agent" className="grid gap-4">
      <MemoryAndModelsCard formState={formState} onFormPatch={onFormPatch} />
      <ProviderOverrideCard formState={formState} onFormPatch={onFormPatch} />
      <RunLimitsCard formState={formState} onFormPatch={onFormPatch} />
      <BulkAndAttachmentsCard formState={formState} onFormPatch={onFormPatch} />
      <ReliabilityCard formState={formState} onFormPatch={onFormPatch} />
    </div>
  );
}

/**
 * CALLING SPEC:
 * - Purpose: render the `SettingsGeneralSection` React UI module.
 * - Inputs: callers that import `frontend/src/features/settings/SettingsGeneralSection.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `SettingsGeneralSection`.
 * - Side effects: React rendering and user event wiring.
 */
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { FormField } from "../../components/ui/form-field";
import { NativeSelect } from "../../components/ui/native-select";
import { Button } from "../../components/ui/button";
import type { SettingsFormPatch, SettingsFormState } from "./types";

interface SettingsGeneralSectionProps {
  formState: SettingsFormState;
  currencyOptions: string[];
  onFormPatch: (patch: SettingsFormPatch) => void;
  onOpenResetDialog: () => void;
  isSaving: boolean;
}

export function SettingsGeneralSection({
  formState,
  currencyOptions,
  onFormPatch,
  onOpenResetDialog,
  isSaving
}: SettingsGeneralSectionProps) {
  return (
    <div id="settings-panel-general" role="tabpanel" aria-labelledby="settings-tab-general" className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Ledger defaults</CardTitle>
          <CardDescription>Defaults used by new entry flows, agent proposals, and dashboard analytics.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Default currency" hint="Used when entry currency is omitted in agent proposals and entry defaults.">
              <NativeSelect
                value={formState.default_currency_code}
                onChange={(event) => onFormPatch({ default_currency_code: event.target.value.toUpperCase() })}
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
                onChange={(event) => onFormPatch({ dashboard_currency_code: event.target.value.toUpperCase() })}
              >
                {currencyOptions.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </NativeSelect>
            </FormField>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Reset overrides</CardTitle>
          <CardDescription>Clear all runtime overrides and fall back to the configured server defaults.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="settings-reset-row">
            <div className="grid gap-1">
              <p className="text-sm font-medium text-foreground">Reset to server defaults</p>
              <p className="text-sm text-muted-foreground">
                This clears saved overrides for currencies, agent settings, provider overrides, and reliability values.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              className="settings-reset-button"
              onClick={onOpenResetDialog}
              disabled={isSaving}
            >
              Reset to server defaults
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

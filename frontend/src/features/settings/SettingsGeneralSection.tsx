import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { FormField } from "../../components/ui/form-field";
import { Input } from "../../components/ui/input";
import { NativeSelect } from "../../components/ui/native-select";
import { Button } from "../../components/ui/button";
import type { SettingsFormPatch, SettingsFormState } from "./types";

interface SettingsGeneralSectionProps {
  currentUserName: string;
  passwordForm: {
    current_password: string;
    new_password: string;
    confirm_new_password: string;
  };
  formState: SettingsFormState;
  currencyOptions: string[];
  onFormPatch: (patch: SettingsFormPatch) => void;
  onPasswordFieldChange: (
    field: "current_password" | "new_password" | "confirm_new_password",
    value: string
  ) => void;
  onPasswordSubmit: () => void;
  onOpenResetDialog: () => void;
  isSaving: boolean;
  isChangingPassword: boolean;
  passwordError: string | null;
}

export function SettingsGeneralSection({
  currentUserName,
  passwordForm,
  formState,
  currencyOptions,
  onFormPatch,
  onPasswordFieldChange,
  onPasswordSubmit,
  onOpenResetDialog,
  isSaving,
  isChangingPassword,
  passwordError,
}: SettingsGeneralSectionProps) {
  return (
    <div id="settings-panel-general" role="tabpanel" aria-labelledby="settings-tab-general" className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
          <CardDescription>Request identity comes from the active principal, not runtime settings overrides.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <FormField label="Current user name" hint="Read-only request principal for this session.">
            <Input value={currentUserName} readOnly />
          </FormField>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Password</CardTitle>
          <CardDescription>Rotate the password for the currently authenticated user.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <FormField label="Current password">
            <Input
              type="password"
              value={passwordForm.current_password}
              onChange={(event) => onPasswordFieldChange("current_password", event.target.value)}
            />
          </FormField>
          <FormField label="New password">
            <Input
              type="password"
              value={passwordForm.new_password}
              onChange={(event) => onPasswordFieldChange("new_password", event.target.value)}
            />
          </FormField>
          <FormField label="Confirm new password">
            <Input
              type="password"
              value={passwordForm.confirm_new_password}
              onChange={(event) => onPasswordFieldChange("confirm_new_password", event.target.value)}
            />
          </FormField>
          <div className="md:col-span-3 flex flex-wrap items-center gap-3">
            <Button type="button" variant="secondary" onClick={onPasswordSubmit} disabled={isChangingPassword}>
              {isChangingPassword ? "Updating password..." : "Change password"}
            </Button>
            {passwordError ? <p className="error">{passwordError}</p> : null}
          </div>
        </CardContent>
      </Card>

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

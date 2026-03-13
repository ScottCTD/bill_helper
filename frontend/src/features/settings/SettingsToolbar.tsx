/**
 * CALLING SPEC:
 * - Purpose: render the `SettingsToolbar` React UI module.
 * - Inputs: callers that import `frontend/src/features/settings/SettingsToolbar.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `SettingsToolbar`.
 * - Side effects: React rendering and user event wiring.
 */
import { Button } from "../../components/ui/button";
import { cn } from "../../lib/utils";
import { SETTINGS_TABS } from "./constants";
import type { SettingsTab } from "./types";

interface SettingsToolbarProps {
  activeTab: SettingsTab;
  onActiveTabChange: (tab: SettingsTab) => void;
  formError: string | null;
  isDirty: boolean;
  isSaving: boolean;
}

export function SettingsToolbar({
  activeTab,
  onActiveTabChange,
  formError,
  isDirty,
  isSaving,
}: SettingsToolbarProps) {
  return (
    <div className="settings-toolbar">
      <div className="settings-toolbar-row">
        <div className="settings-toolbar-leading">
          <div className="settings-toolbar-heading">
            <h2 className="text-xl font-semibold">Settings</h2>
          </div>
          <div className="settings-tab-list" role="tablist" aria-label="Settings sections">
            {SETTINGS_TABS.map((tab) => (
              <Button
                key={tab.id}
                id={`settings-tab-${tab.id}`}
                type="button"
                role="tab"
                aria-controls={`settings-panel-${tab.id}`}
                aria-selected={activeTab === tab.id}
                variant={activeTab === tab.id ? "default" : "outline"}
                size="sm"
                className={cn("settings-tab-button", activeTab === tab.id ? "settings-tab-active" : "")}
                onClick={() => onActiveTabChange(tab.id)}
              >
                {tab.label}
              </Button>
            ))}
          </div>
        </div>
        <div className="settings-toolbar-actions">
          <div className="settings-toolbar-copy">
            <p className="settings-toolbar-title">{isDirty ? "Unsaved changes" : "All changes saved"}</p>
          </div>
          <Button form="runtime-settings-form" type="submit" disabled={!isDirty || isSaving} className="w-full sm:w-auto">
            {isSaving ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </div>
      {formError ? <p className="error">{formError}</p> : null}
    </div>
  );
}

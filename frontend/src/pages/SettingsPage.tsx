import { SettingsAgentSection } from "../features/settings/SettingsAgentSection";
import { SettingsGeneralSection } from "../features/settings/SettingsGeneralSection";
import { ResetSettingsDialog } from "../features/settings/ResetSettingsDialog";
import { SettingsToolbar } from "../features/settings/SettingsToolbar";
import { useSettingsPageModel } from "../features/settings/useSettingsPageModel";

export function SettingsPage() {
  const model = useSettingsPageModel();

  if (model.queries.settingsQuery.isLoading && !model.formState) {
    return <p>Loading settings...</p>;
  }

  if (model.queries.settingsQuery.isError && !model.formState) {
    return <p className="error">Failed to load settings: {(model.queries.settingsQuery.error as Error).message}</p>;
  }

  if (!model.formState || !model.queries.settingsQuery.data) {
    return null;
  }

  return (
    <div className="stack-lg">
      <SettingsToolbar
        activeTab={model.activeTab}
        onActiveTabChange={model.actions.setActiveTab}
        formError={model.formError}
        isDirty={model.isDirty}
        isSaving={model.mutation.isPending}
      />

      <form id="runtime-settings-form" className="grid gap-4" onSubmit={model.actions.submitSettings}>
        {model.activeTab === "general" ? (
          <SettingsGeneralSection
            formState={model.formState}
            currencyOptions={model.currencyOptions}
            onFormPatch={model.actions.patchFormState}
            onOpenResetDialog={() => model.actions.setIsResetDialogOpen(true)}
            isSaving={model.mutation.isPending}
          />
        ) : (
          <SettingsAgentSection formState={model.formState} onFormPatch={model.actions.patchFormState} />
        )}
      </form>

      <ResetSettingsDialog
        open={model.isResetDialogOpen}
        onOpenChange={model.actions.setIsResetDialogOpen}
        onConfirm={model.actions.confirmResetOverrides}
        isPending={model.mutation.isPending}
      />
    </div>
  );
}

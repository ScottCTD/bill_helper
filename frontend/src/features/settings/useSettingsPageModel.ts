import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getRuntimeSettings, listCurrencies, updateRuntimeSettings } from "../../lib/api";
import { invalidateRuntimeSettingsReadModels } from "../../lib/queryInvalidation";
import { queryKeys } from "../../lib/queryKeys";
import { buildSettingsFormState, buildSettingsUpdatePayload, RESET_RUNTIME_SETTINGS_PAYLOAD } from "./formState";
import type { SettingsFormPatch, SettingsFormState, SettingsTab } from "./types";

export function useSettingsPageModel() {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: queryKeys.settings.runtime,
    queryFn: getRuntimeSettings,
  });
  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });

  const [formState, setFormState] = useState<SettingsFormState | null>(null);
  const [initialState, setInitialState] = useState<SettingsFormState | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>("general");
  const [isResetDialogOpen, setIsResetDialogOpen] = useState(false);

  const updateMutation = useMutation({
    mutationFn: updateRuntimeSettings,
    onSuccess: (data) => {
      invalidateRuntimeSettingsReadModels(queryClient);
      const nextFormState = buildSettingsFormState(data);
      setFormState(nextFormState);
      setInitialState(nextFormState);
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
    const nextFormState = buildSettingsFormState(settingsQuery.data);
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

  function patchFormState(patch: SettingsFormPatch) {
    setFormState((state) => (state ? { ...state, ...patch } : state));
  }

  function submitSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!formState) {
      return;
    }
    setFormError(null);
    try {
      updateMutation.mutate(buildSettingsUpdatePayload(formState));
    } catch (error) {
      setFormError((error as Error).message);
    }
  }

  function resetOverrides() {
    updateMutation.mutate(RESET_RUNTIME_SETTINGS_PAYLOAD);
  }

  function confirmResetOverrides() {
    setIsResetDialogOpen(false);
    resetOverrides();
  }

  return {
    formState,
    formError,
    activeTab,
    isDirty,
    isResetDialogOpen,
    currencyOptions,
    queries: {
      settingsQuery,
      currenciesQuery,
    },
    mutation: updateMutation,
    actions: {
      setActiveTab,
      patchFormState,
      submitSettings,
      setIsResetDialogOpen,
      confirmResetOverrides,
    },
  };
}

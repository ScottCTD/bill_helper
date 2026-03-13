/**
 * CALLING SPEC:
 * - Purpose: provide the `usePropertiesSectionState` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/features/properties/usePropertiesSectionState.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `usePropertiesSectionState`.
 * - Side effects: client-side state coordination and query wiring.
 */
import { useState } from "react";

import {
  SECTION_CREATE_PANEL_DEFAULTS,
  SECTION_SEARCH_DEFAULTS,
  type PropertiesSectionId
} from "./types";

export function usePropertiesSectionState() {
  const [activeSection, setActiveSection] = useState<PropertiesSectionId>("tags");
  const [sectionSearch, setSectionSearch] = useState<Record<PropertiesSectionId, string>>({
    ...SECTION_SEARCH_DEFAULTS
  });
  const [createPanelOpen, setCreatePanelOpen] = useState<Record<PropertiesSectionId, boolean>>({
    ...SECTION_CREATE_PANEL_DEFAULTS
  });

  function setSectionSearchValue(sectionId: PropertiesSectionId, value: string) {
    setSectionSearch((state) => ({ ...state, [sectionId]: value }));
  }

  function toggleCreatePanel(sectionId: PropertiesSectionId) {
    setCreatePanelOpen((state) => ({ ...state, [sectionId]: !state[sectionId] }));
  }

  function closeCreatePanel(sectionId: PropertiesSectionId) {
    setCreatePanelOpen((state) => ({ ...state, [sectionId]: false }));
  }

  return {
    activeSection,
    setActiveSection,
    sectionSearch,
    createPanelOpen,
    actions: {
      setSectionSearchValue,
      toggleCreatePanel,
      closeCreatePanel
    }
  };
}

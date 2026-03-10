import { useState } from "react";

import {
  SECTION_CREATE_PANEL_DEFAULTS,
  SECTION_SEARCH_DEFAULTS,
  type PropertiesSectionId
} from "./types";

export function usePropertiesSectionState() {
  const [activeSection, setActiveSection] = useState<PropertiesSectionId>("users");
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

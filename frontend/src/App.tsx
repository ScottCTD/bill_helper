import { Suspense, lazy, useState } from "react";
import { Route, Routes } from "react-router-dom";

import { Sidebar } from "./components/Sidebar";
import { PrincipalSessionGate, usePrincipalSession } from "./features/session";
import { useResizablePanel } from "./hooks/useResizablePanel";

const HomePage = lazy(async () => {
  const module = await import("./pages/HomePage");
  return { default: module.HomePage };
});

const DashboardPage = lazy(async () => {
  const module = await import("./pages/DashboardPage");
  return { default: module.DashboardPage };
});

const FilterGroupsPage = lazy(async () => {
  const module = await import("./pages/FilterGroupsPage");
  return { default: module.FilterGroupsPage };
});

const EntriesPage = lazy(async () => {
  const module = await import("./pages/EntriesPage");
  return { default: module.EntriesPage };
});

const EntitiesPage = lazy(async () => {
  const module = await import("./pages/EntitiesPage");
  return { default: module.EntitiesPage };
});

const EntryDetailPage = lazy(async () => {
  const module = await import("./pages/EntryDetailPage");
  return { default: module.EntryDetailPage };
});

const AccountsPage = lazy(async () => {
  const module = await import("./pages/AccountsPage");
  return { default: module.AccountsPage };
});

const GroupsPage = lazy(async () => {
  const module = await import("./pages/GroupsPage");
  return { default: module.GroupsPage };
});

const PropertiesPage = lazy(async () => {
  const module = await import("./pages/PropertiesPage");
  return { default: module.PropertiesPage };
});

const SettingsPage = lazy(async () => {
  const module = await import("./pages/SettingsPage");
  return { default: module.SettingsPage };
});

function defaultSidebarCollapsed() {
  if (typeof window === "undefined") {
    return false;
  }
  return window.innerWidth <= 768;
}

export function App() {
  const { principalName } = usePrincipalSession();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(defaultSidebarCollapsed);
  const { panelWidth: sidebarWidth, handleMouseDown: handleSidebarResizeMouseDown } = useResizablePanel({
    storageKey: "app-sidebar-width",
    defaultWidth: 224,
    minWidth: 200,
    maxWidth: 320,
    edge: "left"
  });

  if (!principalName) {
    return <PrincipalSessionGate />;
  }

  return (
    <div className="app-shell">
      <Sidebar
        collapsed={sidebarCollapsed}
        width={sidebarWidth}
        onToggle={() => setSidebarCollapsed((c) => !c)}
      />
      {!sidebarCollapsed ? (
        <div
          className="panel-resize-handle app-sidebar-resize-handle"
          onMouseDown={handleSidebarResizeMouseDown}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
        />
      ) : null}

      <main className="app-main app-main-padded">
        <div className="app-content">
          <Suspense fallback={<p>Loading page...</p>}>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/filters" element={<FilterGroupsPage />} />
              <Route path="/entries" element={<EntriesPage />} />
              <Route path="/entities" element={<EntitiesPage />} />
              <Route path="/entries/:entryId" element={<EntryDetailPage />} />
              <Route path="/groups" element={<GroupsPage />} />
              <Route path="/accounts" element={<AccountsPage />} />
              <Route path="/properties" element={<PropertiesPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </Suspense>
        </div>
      </main>
    </div>
  );
}

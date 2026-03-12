import { Suspense, lazy, useEffect, useRef, useState } from "react";
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
  const appMainRef = useRef<HTMLElement | null>(null);
  const { panelWidth: sidebarWidth, handleMouseDown: handleSidebarResizeMouseDown } = useResizablePanel({
    storageKey: "app-sidebar-width",
    defaultWidth: 224,
    minWidth: 200,
    maxWidth: 320,
    edge: "left"
  });

  useEffect(() => {
    if (!(appMainRef.current instanceof HTMLElement)) {
      return;
    }
    const element: HTMLElement = appMainRef.current;

    let clearScrollStateTimeout: number | null = null;

    function markScrolling() {
      element.classList.add("app-main-scroll-active");
      if (clearScrollStateTimeout !== null) {
        window.clearTimeout(clearScrollStateTimeout);
      }
      clearScrollStateTimeout = window.setTimeout(() => {
        element.classList.remove("app-main-scroll-active");
        clearScrollStateTimeout = null;
      }, 420);
    }

    element.addEventListener("scroll", markScrolling, { passive: true });
    return () => {
      element.removeEventListener("scroll", markScrolling);
      if (clearScrollStateTimeout !== null) {
        window.clearTimeout(clearScrollStateTimeout);
      }
      element.classList.remove("app-main-scroll-active");
    };
  }, []);

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

      <main ref={appMainRef} className="app-main app-main-padded">
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

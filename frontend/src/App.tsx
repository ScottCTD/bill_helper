import { Suspense, lazy, useState } from "react";
import { Route, Routes, useLocation } from "react-router-dom";

import { Sidebar } from "./components/Sidebar";
import { cn } from "./lib/utils";

const HomePage = lazy(async () => {
  const module = await import("./pages/HomePage");
  return { default: module.HomePage };
});

const DashboardPage = lazy(async () => {
  const module = await import("./pages/DashboardPage");
  return { default: module.DashboardPage };
});

const EntriesPage = lazy(async () => {
  const module = await import("./pages/EntriesPage");
  return { default: module.EntriesPage };
});

const EntryDetailPage = lazy(async () => {
  const module = await import("./pages/EntryDetailPage");
  return { default: module.EntryDetailPage };
});

const AccountsPage = lazy(async () => {
  const module = await import("./pages/AccountsPage");
  return { default: module.AccountsPage };
});

const PropertiesPage = lazy(async () => {
  const module = await import("./pages/PropertiesPage");
  return { default: module.PropertiesPage };
});

const SettingsPage = lazy(async () => {
  const module = await import("./pages/SettingsPage");
  return { default: module.SettingsPage };
});

export function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const location = useLocation();
  const isAgentPage = location.pathname === "/";

  return (
    <div className="app-shell">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((c) => !c)}
      />

      <main className={cn("app-main", !isAgentPage && "app-main-padded")}>
        <div className={cn(!isAgentPage && "app-content")}>
          <Suspense fallback={<p>Loading page...</p>}>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/entries" element={<EntriesPage />} />
              <Route path="/entries/:entryId" element={<EntryDetailPage />} />
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

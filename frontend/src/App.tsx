import { useState } from "react";
import { Route, Routes, useLocation } from "react-router-dom";

import { Sidebar } from "./components/Sidebar";
import { cn } from "./lib/utils";
import { AccountsPage } from "./pages/AccountsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EntriesPage } from "./pages/EntriesPage";
import { EntryDetailPage } from "./pages/EntryDetailPage";
import { HomePage } from "./pages/HomePage";
import { PropertiesPage } from "./pages/PropertiesPage";
import { SettingsPage } from "./pages/SettingsPage";

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
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/entries" element={<EntriesPage />} />
            <Route path="/entries/:entryId" element={<EntryDetailPage />} />
            <Route path="/accounts" element={<AccountsPage />} />
            <Route path="/properties" element={<PropertiesPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

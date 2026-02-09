import { NavLink, Route, Routes } from "react-router-dom";
import { Bot, CreditCard, FolderKanban, Home, Layers3 } from "lucide-react";

import { buttonVariants } from "./components/ui/button";
import { cn } from "./lib/utils";
import { AccountsPage } from "./pages/AccountsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EntriesPage } from "./pages/EntriesPage";
import { EntryDetailPage } from "./pages/EntryDetailPage";
import { HomePage } from "./pages/HomePage";
import { PropertiesPage } from "./pages/PropertiesPage";

const navItems = [
  { to: "/", label: "Home", icon: Bot },
  { to: "/dashboard", label: "Dashboard", icon: Home },
  { to: "/entries", label: "Entries", icon: Layers3 },
  { to: "/accounts", label: "Accounts", icon: CreditCard },
  { to: "/properties", label: "Properties", icon: FolderKanban }
] as const;

export function App() {
  return (
    <div className="mx-auto max-w-[1220px] px-4 pb-8 pt-5 md:px-7 md:pt-7">
      <header className="mb-6 flex flex-col gap-4 rounded-2xl border bg-card/95 p-5 shadow-sm md:flex-row md:items-center md:justify-between md:p-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Bill Helper</h1>
          <p className="mt-1 text-base text-muted-foreground">Local-first ledger with append-only AI review workflow.</p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) => cn(buttonVariants({ variant: isActive ? "default" : "outline", size: "sm" }))}
              >
                <Icon className="mr-1.5 h-4 w-4" />
                {item.label}
              </NavLink>
            );
          })}
        </div>
      </header>

      <main className="page">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/entries" element={<EntriesPage />} />
          <Route path="/entries/:entryId" element={<EntryDetailPage />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/properties" element={<PropertiesPage />} />
        </Routes>
      </main>
    </div>
  );
}

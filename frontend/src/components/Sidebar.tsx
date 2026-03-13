/**
 * CALLING SPEC:
 * - Purpose: render the `Sidebar` React UI module.
 * - Inputs: callers that import `frontend/src/components/Sidebar.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `Sidebar`.
 * - Side effects: React rendering and user event wiring.
 */
import type { CSSProperties } from "react";
import { NavLink } from "react-router-dom";
import { Bot, Building2, CreditCard, FolderKanban, Home, Layers3, Network, PanelLeft, PanelLeftClose, Settings2, Shield, SlidersHorizontal } from "lucide-react";

import { AuthSessionCard, useAuth } from "../features/auth";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";

const navItems = [
  { to: "/", label: "Agent", icon: Bot },
  { to: "/dashboard", label: "Dashboard", icon: Home },
  { to: "/filters", label: "Filters", icon: SlidersHorizontal },
  { to: "/entries", label: "Entries", icon: Layers3 },
  { to: "/entities", label: "Entities", icon: Building2 },
  { to: "/groups", label: "Groups", icon: Network },
  { to: "/accounts", label: "Accounts", icon: CreditCard },
  { to: "/properties", label: "Properties", icon: FolderKanban },
  { to: "/settings", label: "Settings", icon: Settings2 },
] as const;

interface SidebarProps {
  collapsed: boolean;
  width: number;
  onToggle: () => void;
}

export function Sidebar({ collapsed, width, onToggle }: SidebarProps) {
  const auth = useAuth();
  const sidebarStyle = (!collapsed ? { "--sidebar-width": `${width}px` } : undefined) as CSSProperties | undefined;

  return (
    <aside className={cn("sidebar", collapsed && "sidebar-collapsed")} style={sidebarStyle}>
      <div className="sidebar-header">
        {!collapsed ? <span className="sidebar-title">Bill Helper</span> : null}
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={onToggle}
          className="sidebar-toggle"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </Button>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => cn("sidebar-link", isActive && "sidebar-link-active")}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="sidebar-link-icon" />
              {!collapsed ? <span>{item.label}</span> : null}
            </NavLink>
          );
        })}
      </nav>

      {!collapsed ? (
        <div className="sidebar-footer">
          {auth.status === "authenticated" && auth.session?.user.is_admin ? (
            <NavLink
              to="/admin"
              end
              className={({ isActive }) => cn("sidebar-link", isActive && "sidebar-link-active")}
            >
              <Shield className="sidebar-link-icon" />
              <span>Admin</span>
            </NavLink>
          ) : null}
          <AuthSessionCard />
        </div>
      ) : null}
    </aside>
  );
}

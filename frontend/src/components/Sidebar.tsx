import { NavLink } from "react-router-dom";
import { Bot, CreditCard, FolderKanban, Home, Layers3, Network, Settings2, PanelLeftClose, PanelLeft } from "lucide-react";
import { cn } from "../lib/utils";

const navItems = [
  { to: "/", label: "Agent", icon: Bot },
  { to: "/dashboard", label: "Dashboard", icon: Home },
  { to: "/entries", label: "Entries", icon: Layers3 },
  { to: "/groups", label: "Groups", icon: Network },
  { to: "/accounts", label: "Accounts", icon: CreditCard },
  { to: "/properties", label: "Properties", icon: FolderKanban },
  { to: "/settings", label: "Settings", icon: Settings2 },
] as const;

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <aside
      className={cn(
        "sidebar",
        collapsed && "sidebar-collapsed"
      )}
    >
      <div className="sidebar-header">
        {!collapsed && (
          <span className="sidebar-title">Bill Helper</span>
        )}
        <button
          onClick={onToggle}
          className="sidebar-toggle"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeft className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn("sidebar-link", isActive && "sidebar-link-active")
              }
              title={collapsed ? item.label : undefined}
            >
              <Icon className="sidebar-link-icon" />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {!collapsed && (
        <div className="sidebar-footer">
          <p className="sidebar-footer-text">
            Local-first ledger with AI review
          </p>
        </div>
      )}
    </aside>
  );
}

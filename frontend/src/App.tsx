/**
 * CALLING SPEC:
 * - Purpose: render the `App` React UI module.
 * - Inputs: callers that import `frontend/src/App.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `App`.
 * - Side effects: React rendering and user event wiring.
 */
import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { Sidebar } from "./components/Sidebar";
import { useAuth } from "./features/auth";
import { useResizablePanel } from "./hooks/useResizablePanel";

const HomePage = lazy(async () => {
  const module = await import("./pages/HomePage");
  return { default: module.HomePage };
});

const DashboardPage = lazy(async () => {
  const module = await import("./pages/DashboardPage");
  return { default: module.DashboardPage };
});

const WorkspacePage = lazy(async () => {
  const module = await import("./pages/WorkspacePage");
  return { default: module.WorkspacePage };
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

const LoginPage = lazy(async () => {
  const module = await import("./pages/LoginPage");
  return { default: module.LoginPage };
});

const AdminPage = lazy(async () => {
  const module = await import("./pages/AdminPage");
  return { default: module.AdminPage };
});

function WorkspaceRoutePlaceholder() {
  return null;
}

function defaultSidebarCollapsed() {
  if (typeof window === "undefined") {
    return false;
  }
  return window.innerWidth <= 768;
}

function ProtectedShell() {
  const auth = useAuth();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(defaultSidebarCollapsed);
  const [hasVisitedWorkspace, setHasVisitedWorkspace] = useState(false);
  const appMainRef = useRef<HTMLElement | null>(null);
  const { panelWidth: sidebarWidth, handleMouseDown: handleSidebarResizeMouseDown } = useResizablePanel({
    storageKey: "app-sidebar-width",
    defaultWidth: 224,
    minWidth: 200,
    maxWidth: 320,
    edge: "left"
  });
  const location = useLocation();
  const isWorkspaceRoute = location.pathname === "/workspace";
  const shouldRenderWorkspaceSurface = isWorkspaceRoute || hasVisitedWorkspace;
  const appMainClassName = isWorkspaceRoute ? "app-main app-main-immersive" : "app-main app-main-padded";
  const appContentClassName = isWorkspaceRoute ? "app-content app-content-immersive" : "app-content";

  useEffect(() => {
    if (isWorkspaceRoute) {
      setHasVisitedWorkspace(true);
    }
  }, [isWorkspaceRoute]);

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

  if (auth.status === "loading") {
    return <p>Loading session...</p>;
  }

  if (auth.status !== "authenticated" || !auth.session) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return (
    <div className="app-shell">
      <Sidebar
        collapsed={sidebarCollapsed}
        width={sidebarWidth}
        onToggle={() => setSidebarCollapsed((collapsed) => !collapsed)}
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

      <main ref={appMainRef} className={appMainClassName}>
        <div className={appContentClassName}>
          {auth.session.is_admin_impersonation ? (
            <div className="impersonation-banner">
              Impersonating {auth.session.user.name}. Log out when you want to end this session.
            </div>
          ) : null}
          {shouldRenderWorkspaceSurface ? (
            <Suspense fallback={<p>Loading workspace...</p>}>
              <WorkspacePage isActive={isWorkspaceRoute} />
            </Suspense>
          ) : null}
          <Suspense fallback={<p>Loading page...</p>}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  );
}

function RequireAdmin() {
  const auth = useAuth();
  if (auth.status !== "authenticated" || !auth.session?.user.is_admin) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

export function App() {
  return (
    <Suspense fallback={<p>Loading page...</p>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedShell />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/workspace" element={<WorkspaceRoutePlaceholder />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/filters" element={<FilterGroupsPage />} />
          <Route path="/entries" element={<EntriesPage />} />
          <Route path="/entities" element={<EntitiesPage />} />
          <Route path="/entries/:entryId" element={<EntryDetailPage />} />
          <Route path="/groups" element={<GroupsPage />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/properties" element={<PropertiesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route element={<RequireAdmin />}>
            <Route path="/admin" element={<AdminPage />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}

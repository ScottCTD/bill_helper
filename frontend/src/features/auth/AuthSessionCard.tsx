/**
 * CALLING SPEC:
 * - Purpose: render the `AuthSessionCard` React UI module as a sidebar logout control.
 * - Inputs: callers that import `frontend/src/features/auth/AuthSessionCard.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `AuthSessionCard`.
 * - Side effects: React rendering and user event wiring.
 */
import { LogOut } from "lucide-react";

import { useAuth } from "./AuthProvider";

interface AuthSessionCardProps {
  collapsed?: boolean;
}

export function AuthSessionCard({ collapsed = false }: AuthSessionCardProps) {
  const auth = useAuth();

  if (auth.status !== "authenticated" || !auth.session) {
    return null;
  }

  const logoutLabel = `Logout (${auth.session.user.name})`;

  return (
    <button
      type="button"
      className="sidebar-link"
      onClick={() => void auth.logout()}
      aria-label={collapsed ? logoutLabel : undefined}
      title={collapsed ? logoutLabel : undefined}
    >
      <LogOut className="sidebar-link-icon" />
      {!collapsed ? <span className="sidebar-link-label">{logoutLabel}</span> : null}
    </button>
  );
}

import { Link } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { useAuth } from "./AuthProvider";

export function AuthSessionCard() {
  const auth = useAuth();

  if (auth.status !== "authenticated" || !auth.session) {
    return null;
  }

  return (
    <section className="sidebar-session-card">
      <div className="sidebar-session-copy">
        <p className="sidebar-session-title">Signed In</p>
        <p className="sidebar-session-subtitle">
          {auth.session.user.name}
          {auth.session.is_admin_impersonation ? " (impersonating)" : auth.session.user.is_admin ? " (admin)" : ""}
        </p>
      </div>
      <div className="sidebar-session-actions">
        {auth.session.user.is_admin ? (
          <Button asChild size="sm" variant="secondary">
            <Link to="/admin">Admin</Link>
          </Button>
        ) : null}
        <Button type="button" size="sm" variant="ghost" onClick={() => void auth.logout()}>
          Log out
        </Button>
      </div>
    </section>
  );
}

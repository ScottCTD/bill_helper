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
        <p className="sidebar-session-subtitle">{auth.session.user.name}</p>
      </div>
      <div className="sidebar-session-actions">
        <Button type="button" size="sm" variant="ghost" onClick={() => void auth.logout()}>
          Log out
        </Button>
      </div>
    </section>
  );
}

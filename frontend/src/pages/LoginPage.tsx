import { type FormEvent, useMemo, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { FormField } from "../components/ui/form-field";
import { Input } from "../components/ui/input";
import { useAuth } from "../features/auth";

export function LoginPage() {
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirectTo = useMemo(() => {
    const fromState = location.state as { from?: { pathname?: string } } | null;
    return fromState?.from?.pathname || "/";
  }, [location.state]);

  if (auth.status === "authenticated") {
    return <Navigate to={redirectTo} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await auth.login({ username, password });
      navigate(redirectTo, { replace: true });
    } catch (submissionError) {
      setError((submissionError as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="session-gate">
      <Card className="session-gate-card">
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>Use a password-backed session to access the ledger and agent tools.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={handleSubmit}>
            <FormField label="User name">
              <Input
                autoFocus
                placeholder="e.g. admin"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </FormField>
            <FormField label="Password">
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </FormField>
            {error ? <p className="error">{error}</p> : null}
            <Button type="submit" disabled={isSubmitting || auth.status === "loading"}>
              {isSubmitting ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}

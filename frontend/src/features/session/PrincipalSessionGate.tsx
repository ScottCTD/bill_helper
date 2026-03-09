import { FormEvent, useEffect, useState } from "react";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { FormField } from "../../components/ui/form-field";
import { Input } from "../../components/ui/input";
import { usePrincipalSession } from "./PrincipalSessionProvider";

export function PrincipalSessionGate() {
  const { principalName, setPrincipalName } = usePrincipalSession();
  const [draftName, setDraftName] = useState(principalName ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraftName(principalName ?? "");
    setError(null);
  }, [principalName]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setPrincipalName(draftName);
      setError(null);
    } catch (submissionError) {
      setError((submissionError as Error).message);
    }
  }

  if (principalName) {
    return null;
  }

  return (
    <main className="session-gate">
      <Card className="session-gate-card">
        <CardHeader>
          <CardTitle>Select a local principal</CardTitle>
          <CardDescription>
            Protected routes now require an explicit principal session. Pick the local identity this browser tab should use.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={handleSubmit}>
            <FormField
              label="Principal name"
              hint="Use an existing owner name or bootstrap a local development principal such as admin."
            >
              <Input
                autoFocus
                placeholder="e.g. admin"
                value={draftName}
                onChange={(event) => setDraftName(event.target.value)}
              />
            </FormField>
            {error ? <p className="error">{error}</p> : null}
            <Button type="submit">Start session</Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}

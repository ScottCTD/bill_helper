import { FormEvent, useEffect, useState } from "react";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { usePrincipalSession } from "./PrincipalSessionProvider";

export function PrincipalSessionCard() {
  const { principalName, setPrincipalName, clearPrincipalName } = usePrincipalSession();
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

  return (
    <section className="sidebar-session-card">
      <div className="sidebar-session-copy">
        <p className="sidebar-session-title">Active principal</p>
        <p className="sidebar-session-subtitle">
          {principalName ? `Requests run as ${principalName}.` : "No principal selected."}
        </p>
      </div>
      <form className="sidebar-session-form" onSubmit={handleSubmit}>
        <Input
          value={draftName}
          onChange={(event) => setDraftName(event.target.value)}
          placeholder="e.g. admin"
          aria-label="Active principal name"
        />
        <div className="sidebar-session-actions">
          <Button type="submit" size="sm" variant="secondary">
            Apply
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={clearPrincipalName}>
            Clear
          </Button>
        </div>
      </form>
      {error ? <p className="error text-xs">{error}</p> : null}
    </section>
  );
}

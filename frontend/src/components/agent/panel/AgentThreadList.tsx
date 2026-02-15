import type { AgentThreadSummary } from "../../../lib/types";
import { Button } from "../../ui/button";
import { compactThreadName } from "./format";

interface AgentThreadListProps {
  threads: AgentThreadSummary[] | undefined;
  selectedThreadId: string;
  isLoading: boolean;
  errorMessage: string | null;
  onSelectThread: (threadId: string) => void;
}

export function AgentThreadList(props: AgentThreadListProps) {
  const { threads, selectedThreadId, isLoading, errorMessage, onSelectThread } = props;

  return (
    <>
      <section className="agent-thread-list agent-thread-list-page">
        <h3>Threads</h3>
        {isLoading ? <p>Loading threads...</p> : null}
        {errorMessage ? <p className="error">{errorMessage}</p> : null}
        <div className="agent-thread-list-scroll">
          {(threads ?? []).map((thread) => (
            <Button
              key={thread.id}
              type="button"
              variant="ghost"
              className={thread.id === selectedThreadId ? "agent-thread-button selected" : "agent-thread-button"}
              onClick={() => onSelectThread(thread.id)}
              title={thread.title || "Untitled thread"}
            >
              <span className="agent-thread-label">{compactThreadName(thread)}</span>
            </Button>
          ))}
        </div>
      </section>
    </>
  );
}

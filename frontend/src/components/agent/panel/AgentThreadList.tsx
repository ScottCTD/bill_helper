import { Trash2 } from "lucide-react";

import type { AgentThreadSummary } from "../../../lib/types";
import { Button } from "../../ui/button";
import { compactThreadName } from "./format";

interface AgentThreadListProps {
  threads: AgentThreadSummary[] | undefined;
  selectedThreadId: string;
  isLoading: boolean;
  errorMessage: string | null;
  onSelectThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  deletingThreadId: string | null;
  isDeleteDisabled: boolean;
}

export function AgentThreadList(props: AgentThreadListProps) {
  const { threads, selectedThreadId, isLoading, errorMessage, onSelectThread, onDeleteThread, deletingThreadId, isDeleteDisabled } =
    props;

  return (
    <>
      <section className="agent-thread-list agent-thread-list-page">
        <h3>Threads</h3>
        {isLoading ? <p>Loading threads...</p> : null}
        {errorMessage ? <p className="error">{errorMessage}</p> : null}
        <div className="agent-thread-list-scroll">
          {(threads ?? []).map((thread) => {
            const isSelected = thread.id === selectedThreadId;
            return (
              <div key={thread.id} className={isSelected ? "agent-thread-row group selected" : "agent-thread-row group"}>
                <Button
                  type="button"
                  variant="ghost"
                  className="agent-thread-button"
                  onClick={() => onSelectThread(thread.id)}
                  title={thread.title || "Untitled thread"}
                >
                  <span className="agent-thread-label">{compactThreadName(thread)}</span>
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="agent-thread-delete-button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDeleteThread(thread.id);
                  }}
                  disabled={isDeleteDisabled || deletingThreadId === thread.id}
                  aria-label={`Delete thread ${thread.title || "untitled thread"}`}
                  title="Delete thread"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                </Button>
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}

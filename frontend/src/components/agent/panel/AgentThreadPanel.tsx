import type { AgentThreadSummary } from "../../../lib/types";
import { AgentThreadList } from "./AgentThreadList";

interface AgentThreadPanelProps {
  threads: AgentThreadSummary[] | undefined;
  selectedThreadId: string;
  isLoading: boolean;
  errorMessage: string | null;
  onSelectThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  deletingThreadId: string | null;
  isDeleteDisabled: boolean;
  isOpen: boolean;
  optimisticRunningThreadId: string | null;
}

export function AgentThreadPanel(props: AgentThreadPanelProps) {
  const {
    threads,
    selectedThreadId,
    isLoading,
    errorMessage,
    onSelectThread,
    onDeleteThread,
    deletingThreadId,
    isDeleteDisabled,
    isOpen,
    optimisticRunningThreadId
  } = props;

  if (!isOpen) return null;

  return (
    <div className="agent-thread-panel">
      <div className="agent-thread-panel-header">
        <span className="agent-thread-panel-title">Threads</span>
      </div>
      <AgentThreadList
        threads={threads}
        selectedThreadId={selectedThreadId}
        isLoading={isLoading}
        errorMessage={errorMessage}
        onSelectThread={onSelectThread}
        onDeleteThread={onDeleteThread}
        deletingThreadId={deletingThreadId}
        isDeleteDisabled={isDeleteDisabled}
        optimisticRunningThreadId={optimisticRunningThreadId}
      />
    </div>
  );
}

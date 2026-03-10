import type { AgentThreadSummary } from "../../../lib/types";
import { AgentThreadList } from "./AgentThreadList";

interface AgentThreadPanelProps {
  threads: AgentThreadSummary[] | undefined;
  selectedThreadId: string;
  isLoading: boolean;
  errorMessage: string | null;
  onSelectThread: (threadId: string) => void;
  onRenameThread: (threadId: string, title: string) => Promise<void>;
  onDeleteThread: (threadId: string) => void;
  renamingThreadId: string | null;
  deletingThreadId: string | null;
  deleteDisabledThreadIds: string[];
  renameDisabledThreadIds: string[];
  isOpen: boolean;
  optimisticRunningThreadIds: string[];
}

export function AgentThreadPanel(props: AgentThreadPanelProps) {
  const {
    threads,
    selectedThreadId,
    isLoading,
    errorMessage,
    onSelectThread,
    onRenameThread,
    onDeleteThread,
    renamingThreadId,
    deletingThreadId,
    deleteDisabledThreadIds,
    renameDisabledThreadIds,
    isOpen,
    optimisticRunningThreadIds
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
        onRenameThread={onRenameThread}
        onDeleteThread={onDeleteThread}
        renamingThreadId={renamingThreadId}
        deletingThreadId={deletingThreadId}
        deleteDisabledThreadIds={deleteDisabledThreadIds}
        renameDisabledThreadIds={renameDisabledThreadIds}
        optimisticRunningThreadIds={optimisticRunningThreadIds}
      />
    </div>
  );
}

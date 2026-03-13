/**
 * CALLING SPEC:
 * - Purpose: render the `AgentThreadList` React UI module.
 * - Inputs: callers that import `frontend/src/features/agent/panel/AgentThreadList.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `AgentThreadList`.
 * - Side effects: React rendering and user event wiring.
 */
import { useEffect, useRef, useState } from "react";
import { Loader2, Trash2 } from "lucide-react";

import type { AgentThreadSummary } from "../../../lib/types";
import { displayThreadName } from "./format";

interface AgentThreadListProps {
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
  optimisticRunningThreadIds: string[];
}

function normalizeThreadTitleInput(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

export function AgentThreadList(props: AgentThreadListProps) {
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
    optimisticRunningThreadIds
  } = props;
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);
  const committingThreadIdRef = useRef<string | null>(null);
  const optimisticRunningThreadIdSet = new Set(optimisticRunningThreadIds);
  const deleteDisabledThreadIdSet = new Set(deleteDisabledThreadIds);
  const renameDisabledThreadIdSet = new Set(renameDisabledThreadIds);

  useEffect(() => {
    if (!editingThreadId) {
      return;
    }
    const editor = inputRef.current;
    if (!editor) {
      return;
    }
    editor.focus();
    const end = editor.value.length;
    editor.setSelectionRange(end, end);
  }, [editingThreadId]);

  function beginRename(thread: AgentThreadSummary) {
    if (renameDisabledThreadIdSet.has(thread.id)) {
      return;
    }
    setDraftTitle(thread.title ?? "");
    setEditingThreadId(thread.id);
  }

  function cancelRename() {
    setEditingThreadId(null);
    setDraftTitle("");
  }

  async function commitRename(thread: AgentThreadSummary) {
    if (committingThreadIdRef.current === thread.id) {
      return;
    }
    const nextTitle = normalizeThreadTitleInput(inputRef.current?.value ?? draftTitle);
    const currentTitle = normalizeThreadTitleInput(thread.title ?? "");
    if (!nextTitle || nextTitle === currentTitle) {
      cancelRename();
      return;
    }
    committingThreadIdRef.current = thread.id;
    try {
      await onRenameThread(thread.id, nextTitle);
      cancelRename();
    } finally {
      committingThreadIdRef.current = null;
    }
  }

  return (
    <>
      <section className="agent-thread-list agent-thread-list-page">
        {isLoading ? <p>Loading threads...</p> : null}
        {errorMessage ? <p className="error">{errorMessage}</p> : null}
        <div className="agent-thread-list-scroll scroll-surface">
          {(threads ?? []).map((thread) => {
            const isSelected = thread.id === selectedThreadId;
            const isRunning = thread.has_running_run || optimisticRunningThreadIdSet.has(thread.id);
            const isEditing = editingThreadId === thread.id;
            const threadName = displayThreadName(thread);
            const showDeleteButton = !deleteDisabledThreadIdSet.has(thread.id) && !isEditing;
            const hasActionSlot = isRunning || showDeleteButton;
            const rowClassName = [
              "agent-thread-row group",
              isSelected ? "selected" : null,
              isEditing ? "editing" : null,
              hasActionSlot ? "with-action-slot" : null
            ]
              .filter(Boolean)
              .join(" ");
            const actionSlotClassName = [
              "agent-thread-action-slot",
              showDeleteButton ? "can-delete" : null
            ]
              .filter(Boolean)
              .join(" ");
            return (
              <div key={thread.id} className={rowClassName}>
                {isEditing ? (
                  <div className="agent-thread-edit-slot">
                    <input
                      ref={inputRef}
                      type="text"
                      className="agent-thread-input"
                      aria-label={`Rename thread ${threadName}`}
                      value={draftTitle}
                      disabled={renamingThreadId === thread.id}
                      spellCheck={false}
                      autoCapitalize="none"
                      autoCorrect="off"
                      autoComplete="off"
                      onChange={(event) => {
                        setDraftTitle(event.currentTarget.value);
                      }}
                      onBlur={() => {
                        void commitRename(thread);
                      }}
                      onClick={(event) => event.stopPropagation()}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void commitRename(thread);
                          return;
                        }
                        if (event.key === "Escape") {
                          event.preventDefault();
                          cancelRename();
                        }
                      }}
                    />
                  </div>
                ) : (
                  <button
                    type="button"
                    className="agent-thread-button"
                    onClick={() => onSelectThread(thread.id)}
                    onDoubleClick={() => beginRename(thread)}
                    title={threadName}
                    aria-label={threadName}
                  >
                    <span className="agent-thread-label">{threadName}</span>
                  </button>
                )}
                {hasActionSlot ? (
                  <div className={actionSlotClassName}>
                    {isRunning ? (
                      <span className="agent-thread-status-indicator" role="status" aria-label="Thread is processing">
                        <Loader2 className="agent-thread-running-indicator h-3.5 w-3.5" aria-hidden="true" />
                      </span>
                    ) : null}
                    {showDeleteButton ? (
                      <button
                        type="button"
                        className="agent-thread-delete-button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeleteThread(thread.id);
                        }}
                        disabled={deletingThreadId === thread.id}
                        aria-label={`Delete thread ${threadName}`}
                        title="Delete thread"
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}

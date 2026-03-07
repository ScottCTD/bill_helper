import { useEffect, useRef, useState } from "react";
import { Loader2, Trash2 } from "lucide-react";

import type { AgentThreadSummary } from "../../../lib/types";
import { Button } from "../../../components/ui/button";
import { compactThreadName } from "./format";

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
  isDeleteDisabled: boolean;
  isRenameDisabled: boolean;
  optimisticRunningThreadId: string | null;
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
    isDeleteDisabled,
    isRenameDisabled,
    optimisticRunningThreadId
  } = props;
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const inputRef = useRef<HTMLDivElement | null>(null);
  const committingThreadIdRef = useRef<string | null>(null);
  const initialDraftTitleRef = useRef("");

  useEffect(() => {
    if (!editingThreadId) {
      return;
    }
    const editor = inputRef.current;
    if (!editor) {
      return;
    }
    editor.textContent = initialDraftTitleRef.current;
    editor.focus();
    const selection = window.getSelection();
    if (!selection) {
      return;
    }
    const range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  }, [editingThreadId]);

  function beginRename(thread: AgentThreadSummary) {
    if (isRenameDisabled) {
      return;
    }
    initialDraftTitleRef.current = thread.title ?? "";
    setEditingThreadId(thread.id);
    setDraftTitle(initialDraftTitleRef.current);
  }

  function cancelRename() {
    setEditingThreadId(null);
    setDraftTitle("");
  }

  async function commitRename(thread: AgentThreadSummary) {
    if (committingThreadIdRef.current === thread.id) {
      return;
    }
    const nextTitle = normalizeThreadTitleInput(inputRef.current?.textContent ?? draftTitle);
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
            const isRunning = thread.has_running_run || optimisticRunningThreadId === thread.id;
            const isEditing = editingThreadId === thread.id;
            return (
              <div key={thread.id} className={isSelected ? "agent-thread-row group selected" : "agent-thread-row group"}>
                {isEditing ? (
                  <div className="agent-thread-edit-slot">
                    <div
                      ref={inputRef}
                      role="textbox"
                      contentEditable={renamingThreadId !== thread.id}
                      suppressContentEditableWarning
                      className="agent-thread-input"
                      aria-label={`Rename thread ${thread.title || "untitled thread"}`}
                      aria-multiline={false}
                      onInput={(event) => {
                        setDraftTitle(event.currentTarget.textContent ?? "");
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
                    title={thread.title || "Untitled thread"}
                    aria-label={thread.title || "Untitled thread"}
                  >
                    <span className="agent-thread-label">{compactThreadName(thread)}</span>
                  </button>
                )}
                {isRunning ? (
                  <span className="agent-thread-status-indicator" role="status" aria-label="Thread is processing">
                    <Loader2 className="agent-thread-running-indicator h-3.5 w-3.5" aria-hidden="true" />
                  </span>
                ) : null}
                {!isDeleteDisabled && !isEditing ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="agent-thread-delete-button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onDeleteThread(thread.id);
                    }}
                    disabled={deletingThreadId === thread.id}
                    aria-label={`Delete thread ${thread.title || "untitled thread"}`}
                    title="Delete thread"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  </Button>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}

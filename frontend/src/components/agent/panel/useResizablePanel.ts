import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "agent-thread-panel-width";
const DEFAULT_WIDTH = 300;
const MIN_WIDTH = 200;
const MAX_WIDTH = 600;

export function useResizablePanel() {
  const [panelWidth, setPanelWidth] = useState<number>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = Number(stored);
        if (parsed >= MIN_WIDTH && parsed <= MAX_WIDTH) return parsed;
      }
    } catch {
      // ignore
    }
    return DEFAULT_WIDTH;
  });

  const isDragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const persistWidth = useCallback((width: number) => {
    try {
      localStorage.setItem(STORAGE_KEY, String(width));
    } catch {
      // ignore
    }
  }, []);

  const handleMouseDown = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();
      isDragging.current = true;
      startX.current = event.clientX;
      startWidth.current = panelWidth;
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [panelWidth]
  );

  useEffect(() => {
    function onMouseMove(event: MouseEvent) {
      if (!isDragging.current) return;
      // Dragging leftward from the right panel's left edge increases width
      const delta = startX.current - event.clientX;
      const next = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startWidth.current + delta));
      setPanelWidth(next);
    }

    function onMouseUp() {
      if (!isDragging.current) return;
      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      setPanelWidth((w) => {
        persistWidth(w);
        return w;
      });
    }

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [persistWidth]);

  return { panelWidth, handleMouseDown, MIN_WIDTH, MAX_WIDTH };
}

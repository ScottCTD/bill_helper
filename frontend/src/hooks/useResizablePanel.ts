/**
 * CALLING SPEC:
 * - Purpose: provide the `useResizablePanel` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/hooks/useResizablePanel.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `useResizablePanel`.
 * - Side effects: client-side state coordination and query wiring.
 */
import type { MouseEvent as ReactMouseEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

interface UseResizablePanelOptions {
  storageKey: string;
  defaultWidth: number;
  minWidth: number;
  maxWidth: number;
  edge?: "left" | "right";
}

export function useResizablePanel(options: UseResizablePanelOptions) {
  const { storageKey, defaultWidth, minWidth, maxWidth, edge = "right" } = options;
  const clampWidth = useCallback(
    (width: number) => Math.max(minWidth, Math.min(maxWidth, width)),
    [maxWidth, minWidth]
  );
  const [panelWidth, setPanelWidth] = useState<number>(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        return clampWidth(Number(stored));
      }
    } catch {
      // Ignore storage access failures and fall back to the default width.
    }
    return defaultWidth;
  });

  const isDragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const persistWidth = useCallback(
    (width: number) => {
      try {
        localStorage.setItem(storageKey, String(width));
      } catch {
        // Ignore storage access failures and keep the in-memory width.
      }
    },
    [storageKey]
  );

  const handleMouseDown = useCallback(
    (event: ReactMouseEvent) => {
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
      if (!isDragging.current) {
        return;
      }

      const delta = edge === "left" ? event.clientX - startX.current : startX.current - event.clientX;
      setPanelWidth(clampWidth(startWidth.current + delta));
    }

    function onMouseUp() {
      if (!isDragging.current) {
        return;
      }

      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      setPanelWidth((width) => {
        const nextWidth = clampWidth(width);
        persistWidth(nextWidth);
        return nextWidth;
      });
    }

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [clampWidth, edge, persistWidth]);

  return { panelWidth, handleMouseDown };
}

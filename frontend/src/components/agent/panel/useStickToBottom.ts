import { useCallback, useEffect, useRef, useState } from "react";

const BOTTOM_THRESHOLD_PX = 24;
const SMOOTH_SCROLL_PROGRAMMATIC_GUARD_MS = 400;

function distanceFromBottom(scrollHeight: number, scrollTop: number, clientHeight: number): number {
  return scrollHeight - scrollTop - clientHeight;
}

/**
 * Tracks whether a scrollable container is "stuck" to the bottom.
 * When stuck, any content growth (new elements, text expansion,
 * details open/close) automatically keeps the view at the bottom.
 * Scrolling up detaches; `scrollToBottom` smooth-scrolls back and
 * re-attaches. `snapToBottom` jumps instantly (use on send).
 */
export function useStickToBottom<T extends HTMLElement>() {
  const [containerEl, setContainerEl] = useState<T | null>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const stuckRef = useRef(true);
  const programmaticScroll = useRef(false);
  const prevScrollHeight = useRef(0);
  const smoothScrollReleaseTimer = useRef<number | null>(null);

  const containerRef = useCallback((node: T | null) => {
    setContainerEl((current) => (current === node ? current : node));
  }, []);

  const clearProgrammaticGuardTimer = useCallback(() => {
    if (smoothScrollReleaseTimer.current !== null) {
      window.clearTimeout(smoothScrollReleaseTimer.current);
      smoothScrollReleaseTimer.current = null;
    }
  }, []);

  const markProgrammaticScrollComplete = useCallback(() => {
    clearProgrammaticGuardTimer();
    programmaticScroll.current = false;
  }, [clearProgrammaticGuardTimer]);

  const stick = useCallback(() => {
    stuckRef.current = true;
    setIsAtBottom(true);
  }, []);

  const unstick = useCallback(() => {
    stuckRef.current = false;
    setIsAtBottom(false);
  }, []);

  // Scroll listener — detect manual scroll-away
  useEffect(() => {
    if (!containerEl) {
      return;
    }
    function handleScroll() {
      if (programmaticScroll.current) {
        return;
      }
      const atBottom = distanceFromBottom(containerEl.scrollHeight, containerEl.scrollTop, containerEl.clientHeight) <= BOTTOM_THRESHOLD_PX;
      if (atBottom) {
        stick();
      } else {
        unstick();
      }
    }
    containerEl.addEventListener("scroll", handleScroll, { passive: true });
    return () => containerEl.removeEventListener("scroll", handleScroll);
  }, [containerEl, stick, unstick]);

  // Poll scrollHeight via rAF — catches every kind of size change
  // (new DOM nodes, text content, <details> toggle, CSS transitions).
  useEffect(() => {
    if (!containerEl) {
      return;
    }
    prevScrollHeight.current = containerEl.scrollHeight;
    let rafId: number;

    function tick() {
      const previousHeight = prevScrollHeight.current;
      const newHeight = containerEl.scrollHeight;
      if (newHeight !== previousHeight) {
        const distanceBeforeGrowth = distanceFromBottom(previousHeight, containerEl.scrollTop, containerEl.clientHeight);
        prevScrollHeight.current = newHeight;
        if (stuckRef.current || distanceBeforeGrowth <= BOTTOM_THRESHOLD_PX) {
          stick();
          clearProgrammaticGuardTimer();
          programmaticScroll.current = true;
          containerEl.scrollTop = newHeight;
          programmaticScroll.current = false;
        }
      }
      rafId = requestAnimationFrame(tick);
    }
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [clearProgrammaticGuardTimer, containerEl, stick]);

  // Smooth scroll + re-stick (for the button)
  const scrollToBottom = useCallback(() => {
    if (!containerEl) {
      return;
    }
    stick();
    clearProgrammaticGuardTimer();
    programmaticScroll.current = true;
    containerEl.scrollTo({ top: containerEl.scrollHeight, behavior: "smooth" });
    smoothScrollReleaseTimer.current = window.setTimeout(
      () => markProgrammaticScrollComplete(),
      SMOOTH_SCROLL_PROGRAMMATIC_GUARD_MS
    );
  }, [clearProgrammaticGuardTimer, containerEl, markProgrammaticScrollComplete, stick]);

  // Instant snap (for sending a message / switching threads)
  const snapToBottom = useCallback(() => {
    if (!containerEl) {
      return;
    }
    stick();
    clearProgrammaticGuardTimer();
    programmaticScroll.current = true;
    containerEl.scrollTop = containerEl.scrollHeight;
    programmaticScroll.current = false;
  }, [clearProgrammaticGuardTimer, containerEl, stick]);

  useEffect(() => {
    return () => {
      clearProgrammaticGuardTimer();
    };
  }, [clearProgrammaticGuardTimer]);

  return { containerRef, isAtBottom, scrollToBottom, snapToBottom };
}

import { useCallback, useEffect, useRef, useState } from "react";

const BOTTOM_THRESHOLD_PX = 24;

/**
 * Tracks whether a scrollable container is "stuck" to the bottom.
 * When stuck, any content growth (new elements, text expansion,
 * details open/close) automatically keeps the view at the bottom.
 * Scrolling up detaches; `scrollToBottom` smooth-scrolls back and
 * re-attaches. `snapToBottom` jumps instantly (use on send).
 */
export function useStickToBottom(containerRef: React.RefObject<HTMLElement | null>) {
  const [isAtBottom, setIsAtBottom] = useState(true);
  const stuckRef = useRef(true);
  const programmaticScroll = useRef(false);
  const prevScrollHeight = useRef(0);

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
    const el = containerRef.current;
    if (!el) {
      return;
    }
    function handleScroll() {
      if (programmaticScroll.current) {
        return;
      }
      const atBottom = el!.scrollHeight - el!.scrollTop - el!.clientHeight <= BOTTOM_THRESHOLD_PX;
      if (atBottom) {
        stick();
      } else {
        unstick();
      }
    }
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [containerRef, stick, unstick]);

  // Poll scrollHeight via rAF — catches every kind of size change
  // (new DOM nodes, text content, <details> toggle, CSS transitions).
  useEffect(() => {
    const el = containerRef.current;
    if (!el) {
      return;
    }
    prevScrollHeight.current = el.scrollHeight;
    let rafId: number;

    function tick() {
      const newHeight = el!.scrollHeight;
      if (newHeight !== prevScrollHeight.current) {
        prevScrollHeight.current = newHeight;
        if (stuckRef.current) {
          programmaticScroll.current = true;
          el!.scrollTop = newHeight;
          programmaticScroll.current = false;
        }
      }
      rafId = requestAnimationFrame(tick);
    }
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [containerRef]);

  // Smooth scroll + re-stick (for the button)
  const scrollToBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) {
      return;
    }
    stick();
    programmaticScroll.current = true;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    setTimeout(() => {
      programmaticScroll.current = false;
    }, 400);
  }, [containerRef, stick]);

  // Instant snap (for sending a message / switching threads)
  const snapToBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) {
      return;
    }
    stick();
    programmaticScroll.current = true;
    el.scrollTop = el.scrollHeight;
    programmaticScroll.current = false;
  }, [containerRef, stick]);

  return { isAtBottom, scrollToBottom, snapToBottom };
}

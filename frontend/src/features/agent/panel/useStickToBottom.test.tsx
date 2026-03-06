import { type ReactNode, useState } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { useStickToBottom } from "./useStickToBottom";

interface ScrollMetrics {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
}

function installScrollMetrics(element: HTMLDivElement, initial: ScrollMetrics): ScrollMetrics {
  const metrics: ScrollMetrics = { ...initial };

  Object.defineProperty(element, "scrollTop", {
    configurable: true,
    get: () => metrics.scrollTop,
    set: (value: number) => {
      metrics.scrollTop = value;
    }
  });
  Object.defineProperty(element, "scrollHeight", {
    configurable: true,
    get: () => metrics.scrollHeight
  });
  Object.defineProperty(element, "clientHeight", {
    configurable: true,
    get: () => metrics.clientHeight
  });
  Object.defineProperty(element, "scrollTo", {
    configurable: true,
    value: ({ top }: ScrollToOptions) => {
      if (typeof top === "number") {
        metrics.scrollTop = top;
      }
    }
  });

  return metrics;
}

function HookHarness({ initiallyMounted = true }: { initiallyMounted?: boolean }) {
  const [isMounted, setIsMounted] = useState(initiallyMounted);
  const { containerRef, isAtBottom, scrollToBottom } = useStickToBottom<HTMLDivElement>();

  return (
    <div>
      <button type="button" onClick={() => setIsMounted((value) => !value)}>
        toggle
      </button>
      <button type="button" onClick={scrollToBottom}>
        scroll-to-bottom
      </button>
      <div data-testid="is-at-bottom">{isAtBottom ? "true" : "false"}</div>
      {isMounted ? <div data-testid="container" ref={containerRef} /> : null}
    </div>
  );
}

function renderHarness(ui: ReactNode = <HookHarness />) {
  return render(ui);
}

describe("useStickToBottom", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback: FrameRequestCallback) =>
      window.setTimeout(() => callback(Date.now()), 16)
    );
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation((frameId: number) => {
      window.clearTimeout(frameId);
    });
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("handles delayed mount and toggles isAtBottom on scroll", () => {
    renderHarness(<HookHarness initiallyMounted={false} />);

    expect(screen.queryByTestId("container")).not.toBeInTheDocument();
    expect(screen.getByTestId("is-at-bottom")).toHaveTextContent("true");

    fireEvent.click(screen.getByRole("button", { name: "toggle" }));
    const container = screen.getByTestId("container") as HTMLDivElement;
    const metrics = installScrollMetrics(container, {
      scrollTop: 100,
      scrollHeight: 200,
      clientHeight: 100
    });

    act(() => {
      vi.advanceTimersByTime(20);
    });
    metrics.scrollTop = 100;
    fireEvent.scroll(container);
    expect(screen.getByTestId("is-at-bottom")).toHaveTextContent("true");

    metrics.scrollTop = 20;
    fireEvent.scroll(container);
    expect(screen.getByTestId("is-at-bottom")).toHaveTextContent("false");

    metrics.scrollTop = 100;
    fireEvent.scroll(container);
    expect(screen.getByTestId("is-at-bottom")).toHaveTextContent("true");
  });

  it("follows content growth while stuck to bottom", () => {
    renderHarness();

    const container = screen.getByTestId("container") as HTMLDivElement;
    const metrics = installScrollMetrics(container, {
      scrollTop: 100,
      scrollHeight: 200,
      clientHeight: 100
    });

    fireEvent.scroll(container);
    expect(screen.getByTestId("is-at-bottom")).toHaveTextContent("true");

    metrics.scrollHeight = 360;
    act(() => {
      vi.advanceTimersByTime(20);
    });

    expect(metrics.scrollTop).toBe(360);
    expect(screen.getByTestId("is-at-bottom")).toHaveTextContent("true");
  });

  it("does not auto-follow growth after manual detach", () => {
    renderHarness();

    const container = screen.getByTestId("container") as HTMLDivElement;
    const metrics = installScrollMetrics(container, {
      scrollTop: 100,
      scrollHeight: 200,
      clientHeight: 100
    });

    act(() => {
      vi.advanceTimersByTime(20);
    });
    metrics.scrollTop = 100;
    fireEvent.scroll(container);
    metrics.scrollTop = 24;
    fireEvent.scroll(container);
    expect(screen.getByTestId("is-at-bottom")).toHaveTextContent("false");

    metrics.scrollHeight = 340;
    act(() => {
      vi.advanceTimersByTime(20);
    });

    expect(metrics.scrollTop).toBe(24);
    expect(screen.getByTestId("is-at-bottom")).toHaveTextContent("false");
  });

  it("re-attaches follow mode after scrollToBottom", () => {
    renderHarness();

    const container = screen.getByTestId("container") as HTMLDivElement;
    const metrics = installScrollMetrics(container, {
      scrollTop: 100,
      scrollHeight: 200,
      clientHeight: 100
    });

    act(() => {
      vi.advanceTimersByTime(20);
    });
    metrics.scrollTop = 100;
    fireEvent.scroll(container);
    metrics.scrollTop = 40;
    fireEvent.scroll(container);
    expect(screen.getByTestId("is-at-bottom")).toHaveTextContent("false");

    fireEvent.click(screen.getByRole("button", { name: "scroll-to-bottom" }));
    expect(metrics.scrollTop).toBe(200);
    expect(screen.getByTestId("is-at-bottom")).toHaveTextContent("true");

    metrics.scrollHeight = 330;
    act(() => {
      vi.advanceTimersByTime(20);
    });

    expect(metrics.scrollTop).toBe(330);
    expect(screen.getByTestId("is-at-bottom")).toHaveTextContent("true");
  });
});

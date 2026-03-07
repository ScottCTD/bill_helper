import "@testing-library/jest-dom/vitest";

if (typeof document.elementsFromPoint !== "function") {
  Object.defineProperty(Document.prototype, "elementsFromPoint", {
    configurable: true,
    value: () => []
  });
}

if (typeof window.ResizeObserver !== "function") {
  class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }

  Object.defineProperty(window, "ResizeObserver", {
    configurable: true,
    value: ResizeObserver
  });
}

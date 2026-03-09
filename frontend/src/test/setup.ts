import "@testing-library/jest-dom/vitest";

import { PRINCIPAL_SESSION_STORAGE_KEY } from "../features/session/principalStorage";

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

window.localStorage.setItem(PRINCIPAL_SESSION_STORAGE_KEY, "admin");

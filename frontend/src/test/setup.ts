import "@testing-library/jest-dom/vitest";
import { AUTH_TOKEN_STORAGE_KEY } from "../features/auth/storage";

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

window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);

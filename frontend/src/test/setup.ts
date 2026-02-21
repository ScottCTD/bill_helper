import "@testing-library/jest-dom/vitest";

if (typeof document.elementsFromPoint !== "function") {
  Object.defineProperty(Document.prototype, "elementsFromPoint", {
    configurable: true,
    value: () => []
  });
}

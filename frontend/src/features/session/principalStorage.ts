export const PRINCIPAL_SESSION_STORAGE_KEY = "bill-helper.principal-name";
export const PRINCIPAL_SESSION_CHANGE_EVENT = "bill-helper:principal-changed";
export const PRINCIPAL_SESSION_HEADER_NAME = "X-Bill-Helper-Principal";

function normalizePrincipalName(value: string | null | undefined): string | null {
  const normalized = value?.trim() ?? "";
  return normalized ? normalized.replace(/\s+/g, " ") : null;
}

function readDefaultPrincipalName(): string | null {
  return normalizePrincipalName(import.meta.env.VITE_DEV_PRINCIPAL_NAME);
}

function dispatchPrincipalChange(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new Event(PRINCIPAL_SESSION_CHANGE_EVENT));
}

export function getStoredPrincipalName(): string | null {
  if (typeof window === "undefined") {
    return readDefaultPrincipalName();
  }
  const stored = normalizePrincipalName(window.localStorage.getItem(PRINCIPAL_SESSION_STORAGE_KEY));
  return stored ?? readDefaultPrincipalName();
}

export function setStoredPrincipalName(value: string): string {
  const normalized = normalizePrincipalName(value);
  if (!normalized) {
    throw new Error("Principal name cannot be empty.");
  }
  if (typeof window !== "undefined") {
    window.localStorage.setItem(PRINCIPAL_SESSION_STORAGE_KEY, normalized);
    dispatchPrincipalChange();
  }
  return normalized;
}

export function clearStoredPrincipalName(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(PRINCIPAL_SESSION_STORAGE_KEY);
  dispatchPrincipalChange();
}

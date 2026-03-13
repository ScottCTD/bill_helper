/**
 * CALLING SPEC:
 * - Purpose: provide the `storage` frontend module.
 * - Inputs: callers that import `frontend/src/features/auth/storage.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `storage`.
 * - Side effects: module-local frontend behavior only.
 */
export const AUTH_TOKEN_STORAGE_KEY = "bill-helper.session-token";
export const AUTH_STATE_CHANGE_EVENT = "bill-helper:auth-state-changed";

function dispatchAuthStateChange(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new Event(AUTH_STATE_CHANGE_EVENT));
}

export function getStoredAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const token = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)?.trim() ?? "";
  return token || null;
}

export function setStoredAuthToken(token: string): string {
  const normalized = token.trim();
  if (!normalized) {
    throw new Error("Session token cannot be empty.");
  }
  if (typeof window !== "undefined") {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, normalized);
    dispatchAuthStateChange();
  }
  return normalized;
}

export function clearStoredAuthToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  dispatchAuthStateChange();
}

export function notifyAuthStateChanged(): void {
  dispatchAuthStateChange();
}

/**
 * CALLING SPEC:
 * - Purpose: re-export the public surface for `frontend/src/features/auth`.
 * - Inputs: callers that import `frontend/src/features/auth/index.ts` and pass module-defined arguments or framework events.
 * - Outputs: public exports for `frontend/src/features/auth`.
 * - Side effects: module export wiring only.
 */
export { AuthProvider, useAuth } from "./AuthProvider";
export { AuthSessionCard } from "./AuthSessionCard";
export {
  AUTH_STATE_CHANGE_EVENT,
  AUTH_TOKEN_STORAGE_KEY,
  clearStoredAuthToken,
  getStoredAuthToken,
  notifyAuthStateChanged,
  setStoredAuthToken
} from "./storage";

/**
 * CALLING SPEC:
 * - Purpose: render the `AuthProvider` React UI module.
 * - Inputs: callers that import `frontend/src/features/auth/AuthProvider.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `AuthProvider`.
 * - Side effects: React rendering and user event wiring.
 */
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { getAuthSession, login, loginAsAdminUser, logout, startWorkspace } from "../../lib/api";
import type { AuthLoginResponse, AuthSession } from "../../lib/types";
import {
  AUTH_STATE_CHANGE_EVENT,
  clearStoredAuthToken,
  getStoredAuthToken,
  setStoredAuthToken
} from "./storage";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  session: AuthSession | null;
  login: (payload: { username: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
  adoptLoginResponse: (payload: AuthLoginResponse) => void;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>(() => (getStoredAuthToken() ? "loading" : "unauthenticated"));
  const [session, setSession] = useState<AuthSession | null>(null);
  const autoStartedWorkspaceSessionIdRef = useRef<string | null>(null);

  async function refreshSession() {
    const token = getStoredAuthToken();
    if (!token) {
      setSession(null);
      setStatus("unauthenticated");
      return;
    }

    setStatus("loading");
    try {
      const nextSession = await getAuthSession();
      setSession(nextSession);
      setStatus("authenticated");
    } catch {
      clearStoredAuthToken();
      setSession(null);
      setStatus("unauthenticated");
      queryClient.clear();
    }
  }

  useEffect(() => {
    void refreshSession();
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    function handleAuthStateChange() {
      if (!getStoredAuthToken()) {
        setSession(null);
        setStatus("unauthenticated");
        queryClient.clear();
        return;
      }
      void refreshSession();
    }

    window.addEventListener(AUTH_STATE_CHANGE_EVENT, handleAuthStateChange);
    return () => {
      window.removeEventListener(AUTH_STATE_CHANGE_EVENT, handleAuthStateChange);
    };
  }, [queryClient]);

  useEffect(() => {
    const sessionId = session?.session_id ?? null;
    if (status !== "authenticated" || sessionId === null) {
      autoStartedWorkspaceSessionIdRef.current = null;
      return;
    }
    if (autoStartedWorkspaceSessionIdRef.current === sessionId) {
      return;
    }
    autoStartedWorkspaceSessionIdRef.current = sessionId;
    void startWorkspace().catch(() => undefined);
  }, [session?.session_id, status]);

  async function loginWithPassword(payload: { username: string; password: string }) {
    const response = await login(payload);
    setStoredAuthToken(response.token);
    setSession({
      user: response.user,
      session_id: response.session_id,
      is_admin_impersonation: response.is_admin_impersonation
    });
    setStatus("authenticated");
    queryClient.clear();
  }

  async function logoutCurrentSession() {
    try {
      if (getStoredAuthToken()) {
        await logout();
      }
    } finally {
      clearStoredAuthToken();
      setSession(null);
      setStatus("unauthenticated");
      queryClient.clear();
    }
  }

  function adoptLoginResponse(payload: AuthLoginResponse) {
    setStoredAuthToken(payload.token);
    setSession({
      user: payload.user,
      session_id: payload.session_id,
      is_admin_impersonation: payload.is_admin_impersonation
    });
    setStatus("authenticated");
    queryClient.clear();
  }

  return (
    <AuthContext.Provider
      value={{
        status,
        session,
        login: loginWithPassword,
        logout: logoutCurrentSession,
        adoptLoginResponse,
        refreshSession
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }
  return context;
}

export async function loginAsUserAndAdopt(
  userId: string,
  adoptLoginResponse: (payload: AuthLoginResponse) => void
) {
  const response = await loginAsAdminUser(userId);
  adoptLoginResponse(response);
}

/**
 * CALLING SPEC:
 * - Purpose: define authentication and admin-session contracts for the frontend.
 * - Inputs: frontend modules that manage login state and admin impersonation flows.
 * - Outputs: auth and admin session interfaces.
 * - Side effects: type declarations only.
 */

export interface AuthUser {
  id: string;
  name: string;
  is_admin: boolean;
}

export interface AuthSession {
  user: AuthUser;
  session_id: string | null;
  is_admin_impersonation: boolean;
}

export interface AuthLoginResponse extends AuthSession {
  token: string;
}

export interface AdminSession {
  id: string;
  user_id: string;
  user_name: string;
  is_admin: boolean;
  is_admin_impersonation: boolean;
  created_at: string;
  expires_at: string | null;
  is_current: boolean;
}

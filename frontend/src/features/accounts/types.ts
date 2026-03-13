/**
 * CALLING SPEC:
 * - Purpose: provide the `types` frontend module.
 * - Inputs: callers that import `frontend/src/features/accounts/types.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `types`.
 * - Side effects: module-local frontend behavior only.
 */
export interface AccountFormState {
  owner_user_id: string;
  name: string;
  markdown_body: string;
  currency_code: string;
  is_active: boolean;
}

export interface SnapshotFormState {
  snapshot_at: string;
  balance_major: string;
  note: string;
}

export const TODAY_ISO = new Date().toISOString().slice(0, 10);

export const ACCOUNT_FORM_DEFAULTS: AccountFormState = {
  owner_user_id: "",
  name: "",
  markdown_body: "",
  currency_code: "CAD",
  is_active: true
};

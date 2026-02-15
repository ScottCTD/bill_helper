import type { Account } from "../../lib/types";
import type { AccountFormState } from "./types";

export function toDateLabel(value: string) {
  if (!value) {
    return "-";
  }
  return value.slice(0, 10);
}

export function normalizeOptionalText(value: string): string | undefined {
  const normalized = value.trim();
  return normalized ? normalized : undefined;
}

export function normalizeNullableText(value: string): string | null {
  const normalized = value.trim();
  return normalized ? normalized : null;
}

export function buildEditForm(account: Account, fallbackOwnerUserId: string): AccountFormState {
  return {
    owner_user_id: account.owner_user_id ?? fallbackOwnerUserId,
    name: account.name,
    institution: account.institution ?? "",
    account_type: account.account_type ?? "",
    currency_code: account.currency_code,
    is_active: account.is_active
  };
}

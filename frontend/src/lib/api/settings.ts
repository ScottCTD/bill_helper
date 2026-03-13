/**
 * CALLING SPEC:
 * - Purpose: expose runtime-settings API calls for the frontend.
 * - Inputs: runtime settings update payloads.
 * - Outputs: runtime settings read models.
 * - Side effects: HTTP requests only.
 */

import type { RuntimeSettings, RuntimeSettingsUpdatePayload } from "../types";
import { request } from "./core";

export function getRuntimeSettings(): Promise<RuntimeSettings> {
  return request<RuntimeSettings>("/api/v1/settings");
}

export function updateRuntimeSettings(payload: RuntimeSettingsUpdatePayload): Promise<RuntimeSettings> {
  return request<RuntimeSettings>("/api/v1/settings", {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

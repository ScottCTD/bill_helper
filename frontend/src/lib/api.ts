/**
 * CALLING SPEC:
 * - Purpose: provide a thin compatibility barrel for frontend API modules.
 * - Inputs: frontend modules that still import the legacy `frontend/src/lib/api.ts` path.
 * - Outputs: re-exported domain API modules and shared request helpers.
 * - Side effects: module export wiring only.
 */

export * from "./api/accounts";
export * from "./api/admin";
export * from "./api/agent";
export * from "./api/auth";
export * from "./api/catalogs";
export * from "./api/core";
export * from "./api/dashboard";
export * from "./api/entries";
export * from "./api/filterGroups";
export * from "./api/groups";
export * from "./api/settings";

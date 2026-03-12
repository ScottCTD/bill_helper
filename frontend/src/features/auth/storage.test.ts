import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import {
  AUTH_STATE_CHANGE_EVENT,
  AUTH_TOKEN_STORAGE_KEY,
  clearStoredAuthToken,
  getStoredAuthToken,
  setStoredAuthToken,
} from "./storage";

describe("auth storage", () => {
  beforeEach(() => {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  });

  it("stores trimmed tokens and emits an auth-state event", () => {
    const handler = vi.fn();
    window.addEventListener(AUTH_STATE_CHANGE_EVENT, handler);

    const stored = setStoredAuthToken("  test-token  ");

    expect(stored).toBe("test-token");
    expect(getStoredAuthToken()).toBe("test-token");
    expect(handler).toHaveBeenCalledTimes(1);

    window.removeEventListener(AUTH_STATE_CHANGE_EVENT, handler);
  });

  it("clears the token and emits an auth-state event", () => {
    const handler = vi.fn();
    window.addEventListener(AUTH_STATE_CHANGE_EVENT, handler);
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, "value");

    clearStoredAuthToken();

    expect(getStoredAuthToken()).toBeNull();
    expect(handler).toHaveBeenCalledTimes(1);

    window.removeEventListener(AUTH_STATE_CHANGE_EVENT, handler);
  });
});

import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SettingsPage } from "./SettingsPage";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import type { RuntimeSettings } from "../lib/types";
import { getRuntimeSettings, listCurrencies, updateRuntimeSettings } from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    getRuntimeSettings: vi.fn(),
    listCurrencies: vi.fn(),
    updateRuntimeSettings: vi.fn(),
  };
});

const baseSettingsFixture: RuntimeSettings = {
  current_user_name: "Alice",
  user_memory: null,
  default_currency_code: "CAD",
  dashboard_currency_code: "CAD",
  agent_model: "openrouter/qwen/qwen3.5-27b",
  available_agent_models: [
    "bedrock/us.anthropic.claude-sonnet-4-6",
    "openai/gpt-4.1-mini",
    "openrouter/qwen/qwen3.5-27b",
  ],
  agent_max_steps: 20,
  agent_bulk_max_concurrent_threads: 4,
  agent_retry_max_attempts: 2,
  agent_retry_initial_wait_seconds: 1,
  agent_retry_max_wait_seconds: 8,
  agent_retry_backoff_multiplier: 2,
  agent_max_image_size_bytes: 5_000_000,
  agent_max_images_per_message: 4,
  agent_base_url: null,
  agent_api_key_configured: false,
  overrides: {
    current_user_name: null,
    user_memory: null,
    default_currency_code: null,
    dashboard_currency_code: null,
    agent_model: null,
    available_agent_models: null,
    agent_max_steps: null,
    agent_bulk_max_concurrent_threads: null,
    agent_retry_max_attempts: null,
    agent_retry_initial_wait_seconds: null,
    agent_retry_max_wait_seconds: null,
    agent_retry_backoff_multiplier: null,
    agent_max_image_size_bytes: null,
    agent_max_images_per_message: null,
    agent_base_url: null,
    agent_api_key_configured: false,
  },
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("SettingsPage", () => {
  it("shows server env state when no stored provider override exists", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue({
      ...baseSettingsFixture,
      agent_api_key_configured: true,
    });

    renderWithQueryClient(<SettingsPage />);

    expect(await screen.findByText("Settings")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Use custom provider override" })).toHaveAttribute("aria-checked", "false");
    expect(screen.queryByRole("textbox", { name: "Custom API endpoint" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Custom API key")).not.toBeInTheDocument();
  });

  it("hydrates default model separately from the ordered available-model list", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(baseSettingsFixture);

    renderWithQueryClient(<SettingsPage />);

    expect(await screen.findByLabelText("Default model")).toHaveValue("openrouter/qwen/qwen3.5-27b");
    expect(screen.getByLabelText("Available models")).toHaveValue(
      "bedrock/us.anthropic.claude-sonnet-4-6\nopenai/gpt-4.1-mini\nopenrouter/qwen/qwen3.5-27b"
    );
  });

  it("clears stored provider override when the toggle is turned off and saved", async () => {
    const settingsWithOverride: RuntimeSettings = {
      ...baseSettingsFixture,
      agent_model: "openrouter/stepfun/step-3.5-flash",
      agent_base_url: "https://api.stepfun.example/v1",
      agent_api_key_configured: true,
      overrides: {
        ...baseSettingsFixture.overrides,
        agent_base_url: "https://api.stepfun.example/v1",
        agent_api_key_configured: true,
      },
    };

    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(settingsWithOverride);
    vi.mocked(updateRuntimeSettings).mockResolvedValue({
      ...settingsWithOverride,
      agent_base_url: null,
      agent_api_key_configured: true,
      overrides: {
        ...settingsWithOverride.overrides,
        agent_base_url: null,
        agent_api_key_configured: false,
      },
    });

    renderWithQueryClient(<SettingsPage />);

    const providerOverrideSwitch = await screen.findByRole("switch", { name: "Use custom provider override" });
    expect(providerOverrideSwitch).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("textbox", { name: "Custom API endpoint" })).toBeInTheDocument();
    expect(screen.getByLabelText("Custom API key")).toBeInTheDocument();

    await userEvent.click(providerOverrideSwitch);
    const saveButton = screen.getByRole("button", { name: "Save changes" });
    expect(saveButton).toBeEnabled();
    expect(screen.queryByRole("textbox", { name: "Custom API endpoint" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Custom API key")).not.toBeInTheDocument();
    fireEvent.submit(document.getElementById("runtime-settings-form") as HTMLFormElement);

    await waitFor(() => {
      expect(updateRuntimeSettings).toHaveBeenCalled();
    });
    expect(vi.mocked(updateRuntimeSettings).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        agent_base_url: null,
        agent_api_key: null,
      })
    );
  });

  it("saves agent memory as list items", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue({
      ...baseSettingsFixture,
      user_memory: ["Prefers terse answers."],
      overrides: {
        ...baseSettingsFixture.overrides,
        user_memory: ["Prefers terse answers."],
      },
    });
    vi.mocked(updateRuntimeSettings).mockResolvedValue(baseSettingsFixture);

    renderWithQueryClient(<SettingsPage />);

    await screen.findByText("Agent memory");
    const memoryInput = screen.getByLabelText("Agent memory");
    expect(memoryInput).toHaveValue("Prefers terse answers.");

    await userEvent.clear(memoryInput);
    await userEvent.type(memoryInput, "Prefers terse answers.\n- Works in CAD.");
    fireEvent.submit(document.getElementById("runtime-settings-form") as HTMLFormElement);

    await waitFor(() => {
      expect(updateRuntimeSettings).toHaveBeenCalled();
    });
    expect(vi.mocked(updateRuntimeSettings).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        user_memory: ["Prefers terse answers.", "Works in CAD."],
      })
    );
  });

  it("submits default model separately from ordered available models", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(baseSettingsFixture);
    vi.mocked(updateRuntimeSettings).mockResolvedValue({
      ...baseSettingsFixture,
      agent_model: "google/gemini-2.5-pro",
      available_agent_models: [
        "openai/gpt-4.1-mini",
        "bedrock/us.anthropic.claude-sonnet-4-6",
        "google/gemini-2.5-pro",
      ],
      overrides: {
        ...baseSettingsFixture.overrides,
        agent_model: "google/gemini-2.5-pro",
        available_agent_models: ["openai/gpt-4.1-mini", "bedrock/us.anthropic.claude-sonnet-4-6"],
      },
    });

    renderWithQueryClient(<SettingsPage />);

    const defaultModelInput = await screen.findByLabelText("Default model");
    const availableModelsInput = screen.getByLabelText("Available models");

    await userEvent.clear(defaultModelInput);
    await userEvent.type(defaultModelInput, "google/gemini-2.5-pro");
    await userEvent.clear(availableModelsInput);
    await userEvent.type(
      availableModelsInput,
      "openai/gpt-4.1-mini\n\nbedrock/us.anthropic.claude-sonnet-4-6\nopenai/gpt-4.1-mini"
    );
    fireEvent.submit(document.getElementById("runtime-settings-form") as HTMLFormElement);

    await waitFor(() => {
      expect(updateRuntimeSettings).toHaveBeenCalled();
    });
    expect(vi.mocked(updateRuntimeSettings).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        agent_model: "google/gemini-2.5-pro",
        available_agent_models: ["openai/gpt-4.1-mini", "bedrock/us.anthropic.claude-sonnet-4-6"],
      })
    );
  });

  it("saves Bulk mode max concurrent threads", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(baseSettingsFixture);
    vi.mocked(updateRuntimeSettings).mockResolvedValue({
      ...baseSettingsFixture,
      agent_bulk_max_concurrent_threads: 6,
      overrides: {
        ...baseSettingsFixture.overrides,
        agent_bulk_max_concurrent_threads: 6,
      },
    });

    renderWithQueryClient(<SettingsPage />);

    await screen.findByText("Settings");
    const bulkConcurrencyInput = screen.getByRole("spinbutton", {
      name: "Bulk max threads Maximum fresh threads Bulk mode starts at once."
    });
    await userEvent.clear(bulkConcurrencyInput);
    await userEvent.type(bulkConcurrencyInput, "6");
    fireEvent.submit(document.getElementById("runtime-settings-form") as HTMLFormElement);

    await waitFor(() => {
      expect(updateRuntimeSettings).toHaveBeenCalled();
    });
    expect(vi.mocked(updateRuntimeSettings).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        agent_bulk_max_concurrent_threads: 6,
      })
    );
  });

  it("resets available models and default model to server defaults", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(baseSettingsFixture);
    vi.mocked(updateRuntimeSettings).mockResolvedValue(baseSettingsFixture);

    renderWithQueryClient(<SettingsPage />);

    await screen.findByText("Settings");
    await userEvent.click(screen.getByRole("button", { name: "Reset to server defaults" }));

    await waitFor(() => {
      expect(updateRuntimeSettings).toHaveBeenCalled();
    });
    expect(vi.mocked(updateRuntimeSettings).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        agent_model: null,
        available_agent_models: [],
      })
    );
  });
});

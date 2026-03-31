import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
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
  user_memory: null,
  default_currency_code: "CAD",
  dashboard_currency_code: "CAD",
  agent_model: "openrouter/qwen/qwen3.5-27b",
  entry_tagging_model: null,
  available_agent_models: [
    "bedrock/us.anthropic.claude-sonnet-4-6",
    "openai/gpt-4.1-mini",
    "openrouter/qwen/qwen3.5-27b",
  ],
  agent_model_display_names: {
    "bedrock/us.anthropic.claude-sonnet-4-6": "Claude Sonnet 4.6",
    "openrouter/qwen/qwen3.5-27b": "Qwen 3.5 27B",
  },
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
    user_memory: null,
    default_currency_code: null,
    dashboard_currency_code: null,
    agent_model: null,
    entry_tagging_model: null,
    available_agent_models: null,
    agent_model_display_names: null,
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

async function openAgentTab() {
  await userEvent.click(await screen.findByRole("tab", { name: "Agent" }));
}

describe("SettingsPage", () => {
  it("shows tabbed sections and defaults to the General tab", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(baseSettingsFixture);

    renderWithQueryClient(<SettingsPage />);

    expect(await screen.findByRole("tab", { name: "General" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Agent" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Ledger defaults")).toBeInTheDocument();
    expect(screen.queryByText("Identity")).not.toBeInTheDocument();
    expect(screen.queryByText("Password")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Change password" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
    expect(screen.getByText("All changes saved")).toBeInTheDocument();
    expect(screen.queryByText(/^Default model:/)).not.toBeInTheDocument();
    expect(screen.queryByText("Memory and models")).not.toBeInTheDocument();
  });

  it("shows server env state when no stored provider override exists", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue({
      ...baseSettingsFixture,
      agent_api_key_configured: true,
    });

    renderWithQueryClient(<SettingsPage />);

    await screen.findByRole("tab", { name: "General" });
    await openAgentTab();
    expect(screen.getByRole("switch", { name: "Use custom provider override" })).toHaveAttribute("aria-checked", "false");
    expect(screen.queryByRole("textbox", { name: "Custom API endpoint" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Custom API key")).not.toBeInTheDocument();
  });

  it("hydrates default model separately from the ordered available-model list", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(baseSettingsFixture);

    renderWithQueryClient(<SettingsPage />);

    await openAgentTab();
    const defaultModelInput = await screen.findByLabelText("Default model");
    expect(defaultModelInput).toHaveValue("openrouter/qwen/qwen3.5-27b");
    expect(screen.getByLabelText("Default tagging model")).toHaveValue("");
    const modelIdInputs = screen.getAllByRole("textbox", { name: /Model id, row/ });
    expect(modelIdInputs).toHaveLength(3);
    expect(modelIdInputs[0]).toHaveValue("bedrock/us.anthropic.claude-sonnet-4-6");
    expect(modelIdInputs[1]).toHaveValue("openai/gpt-4.1-mini");
    expect(modelIdInputs[2]).toHaveValue("openrouter/qwen/qwen3.5-27b");
    expect(Array.from(defaultModelInput.querySelectorAll("option")).map((option) => option.textContent)).toEqual([
      "Claude Sonnet 4.6",
      "openai/gpt-4.1-mini",
      "Qwen 3.5 27B",
    ]);
  });

  it("saves the default tagging model from the available model list", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(baseSettingsFixture);
    vi.mocked(updateRuntimeSettings).mockResolvedValue({
      ...baseSettingsFixture,
      entry_tagging_model: "openai/gpt-4.1-mini",
      overrides: {
        ...baseSettingsFixture.overrides,
        entry_tagging_model: "openai/gpt-4.1-mini",
      },
    });

    renderWithQueryClient(<SettingsPage />);

    await openAgentTab();
    const taggingModelInput = await screen.findByLabelText("Default tagging model");
    expect(taggingModelInput).toHaveValue("");

    await userEvent.selectOptions(taggingModelInput, "openai/gpt-4.1-mini");
    fireEvent.submit(document.getElementById("runtime-settings-form") as HTMLFormElement);

    await waitFor(() => {
      expect(updateRuntimeSettings).toHaveBeenCalled();
    });
    expect(vi.mocked(updateRuntimeSettings).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        entry_tagging_model: "openai/gpt-4.1-mini",
      })
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
      entry_tagging_model: null,
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
        entry_tagging_model: null,
        agent_base_url: null,
        agent_api_key_configured: false,
      },
    });

    renderWithQueryClient(<SettingsPage />);

    await openAgentTab();
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

    await openAgentTab();
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

    await openAgentTab();
    const defaultModelInput = await screen.findByLabelText("Default model");

    await userEvent.selectOptions(defaultModelInput, "openai/gpt-4.1-mini");

    // Edit row 1 before row 0 so we never have two identical openai/gpt-4.1-mini ids before the next edit (dedupe would drop a row).
    await act(async () => {
      fireEvent.change(screen.getAllByRole("textbox", { name: /Model id, row/ })[1]!, {
        target: { value: "google/gemini-2.5-pro" },
      });
    });
    await waitFor(() => {
      expect(screen.getAllByRole("textbox", { name: /Model id, row/ })[1]).toHaveValue("google/gemini-2.5-pro");
    });
    await act(async () => {
      fireEvent.change(screen.getAllByRole("textbox", { name: /Model id, row/ })[0]!, {
        target: { value: "openai/gpt-4.1-mini" },
      });
    });
    await waitFor(() => {
      expect(screen.getAllByRole("textbox", { name: /Model id, row/ })[0]).toHaveValue("openai/gpt-4.1-mini");
    });
    await act(async () => {
      fireEvent.change(screen.getAllByRole("textbox", { name: /Model id, row/ })[2]!, {
        target: { value: "bedrock/us.anthropic.claude-sonnet-4-6" },
      });
    });
    await waitFor(() => {
      expect(screen.getAllByRole("textbox", { name: /Model id, row/ })[2]).toHaveValue("bedrock/us.anthropic.claude-sonnet-4-6");
    });

    await waitFor(() => {
      const select = screen.getByLabelText("Default model") as HTMLSelectElement;
      const values = [...select.options].map((option) => option.value).filter(Boolean);
      expect(values).toEqual(
        expect.arrayContaining([
          "openai/gpt-4.1-mini",
          "google/gemini-2.5-pro",
          "bedrock/us.anthropic.claude-sonnet-4-6",
        ])
      );
    });

    await userEvent.selectOptions(screen.getByLabelText("Default model"), "google/gemini-2.5-pro");
    fireEvent.submit(document.getElementById("runtime-settings-form") as HTMLFormElement);

    await waitFor(() => {
      expect(updateRuntimeSettings).toHaveBeenCalled();
    });
    expect(vi.mocked(updateRuntimeSettings).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        agent_model: "google/gemini-2.5-pro",
        available_agent_models: [
          "openai/gpt-4.1-mini",
          "google/gemini-2.5-pro",
          "bedrock/us.anthropic.claude-sonnet-4-6",
        ],
      })
    );
  });

  it("moves the default model to the first remaining option when the selected model is removed from the available list", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(baseSettingsFixture);

    renderWithQueryClient(<SettingsPage />);

    await openAgentTab();
    const defaultModelInput = await screen.findByLabelText("Default model");

    expect(defaultModelInput).toHaveValue("openrouter/qwen/qwen3.5-27b");

    await userEvent.click(screen.getByRole("button", { name: "Remove model row 3" }));

    expect(defaultModelInput).toHaveValue("bedrock/us.anthropic.claude-sonnet-4-6");
  });

  it("clears the tagging model when its available model is removed", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue({
      ...baseSettingsFixture,
      entry_tagging_model: "openrouter/qwen/qwen3.5-27b",
      overrides: {
        ...baseSettingsFixture.overrides,
        entry_tagging_model: "openrouter/qwen/qwen3.5-27b",
      },
    });

    renderWithQueryClient(<SettingsPage />);

    await openAgentTab();
    const taggingModelInput = await screen.findByLabelText("Default tagging model");

    expect(taggingModelInput).toHaveValue("openrouter/qwen/qwen3.5-27b");

    await userEvent.click(screen.getByRole("button", { name: "Remove model row 3" }));

    expect(taggingModelInput).toHaveValue("");
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

    await openAgentTab();
    const bulkConcurrencyInput = screen.getByLabelText("Bulk concurrent launches");
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

  it("resets available models and default model to server defaults from the General tab dialog", async () => {
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(baseSettingsFixture);
    vi.mocked(updateRuntimeSettings).mockResolvedValue(baseSettingsFixture);

    renderWithQueryClient(<SettingsPage />);

    await screen.findByText("Reset overrides");
    await userEvent.click(screen.getByRole("button", { name: "Reset to server defaults" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Reset all runtime overrides?")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Reset to server defaults" }));

    await waitFor(() => {
      expect(updateRuntimeSettings).toHaveBeenCalled();
    });
    expect(vi.mocked(updateRuntimeSettings).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        agent_model: null,
        entry_tagging_model: null,
        available_agent_models: [],
        agent_model_display_names: null,
      })
    );
  });
});

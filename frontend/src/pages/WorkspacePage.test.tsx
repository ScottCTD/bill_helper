import { useState } from "react";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspacePage } from "./WorkspacePage";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import type { WorkspaceIdeSession, WorkspaceSnapshot } from "../lib/types";
import { createWorkspaceIdeSession, getWorkspaceSnapshot } from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    createWorkspaceIdeSession: vi.fn(),
    getWorkspaceSnapshot: vi.fn(),
  };
});

const baseSnapshot: WorkspaceSnapshot = {
  workspace_enabled: true,
  starts_on_login: true,
  status: "created",
  container_name: "bill-helper-sandbox-user-1",
  volume_name: "bill-helper-workspace-user-1",
  ide_ready: false,
  ide_launch_path: "/api/v1/workspace/ide/",
  degraded_reason: "Start workspace to launch the IDE.",
};

const liveSnapshot: WorkspaceSnapshot = {
  ...baseSnapshot,
  status: "running",
  ide_ready: true,
  degraded_reason: null,
};

const imageMissingSnapshot: WorkspaceSnapshot = {
  ...baseSnapshot,
  status: "image_missing",
  degraded_reason: "Agent workspace image is missing. Build Docker image `bill-helper-agent-workspace:latest` before starting the workspace."
};

const liveSession: WorkspaceIdeSession = {
  launch_url: "/api/v1/workspace/ide/?folder=/workspace",
  snapshot: liveSnapshot
};

function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

beforeEach(() => {
  mockMatchMedia(false);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("WorkspacePage", () => {
  it("auto-launches the IDE on desktop and keeps the full-bleed IDE visible", async () => {
    vi.mocked(getWorkspaceSnapshot).mockResolvedValue(baseSnapshot);
    vi.mocked(createWorkspaceIdeSession).mockResolvedValue(liveSession);

    renderWithQueryClient(
      <MemoryRouter>
        <WorkspacePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(createWorkspaceIdeSession).toHaveBeenCalledTimes(1);
    });

    expect(
      screen.getByRole("status", { name: "Loading workspace IDE" }),
    ).toBeInTheDocument();

    const frame = screen.getByTitle("Workspace IDE");
    expect(frame).toHaveAttribute(
      "src",
      "/api/v1/workspace/ide/?folder=/workspace"
    );
    fireEvent.load(frame);

    await waitFor(() => {
      expect(
        screen.queryByRole("status", { name: "Loading workspace IDE" }),
      ).not.toBeInTheDocument();
    });
  });

  it("shows the image-missing degraded state", async () => {
    vi.mocked(getWorkspaceSnapshot).mockResolvedValue(imageMissingSnapshot);

    renderWithQueryClient(
      <MemoryRouter>
        <WorkspacePage />
      </MemoryRouter>
    );

    expect((await screen.findAllByText("Image missing")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/agent workspace image is missing/i).length).toBeGreaterThan(0);
    expect(createWorkspaceIdeSession).not.toHaveBeenCalled();
    expect(screen.queryByText("Auto-start on login")).not.toBeInTheDocument();
    expect(screen.queryByText("/data")).not.toBeInTheDocument();
  });

  it("shows only the desktop-first message on narrow screens", async () => {
    mockMatchMedia(true);
    vi.mocked(getWorkspaceSnapshot).mockResolvedValue(baseSnapshot);

    renderWithQueryClient(
      <MemoryRouter>
        <WorkspacePage />
      </MemoryRouter>
    );

    expect(await screen.findByText("Workspace IDE is desktop-first")).toBeInTheDocument();
    expect(createWorkspaceIdeSession).not.toHaveBeenCalled();
  });

  it("waits for the route to become active before launching and keeps the IDE session across deactivation", async () => {
    vi.mocked(getWorkspaceSnapshot).mockResolvedValue(baseSnapshot);
    vi.mocked(createWorkspaceIdeSession).mockResolvedValue(liveSession);

    function Harness() {
      const [isActive, setIsActive] = useState(false);
      return (
        <MemoryRouter>
          <button type="button" onClick={() => setIsActive((current) => !current)}>
            Toggle workspace
          </button>
          <WorkspacePage isActive={isActive} />
        </MemoryRouter>
      );
    }

    renderWithQueryClient(
      <Harness />
    );

    expect(createWorkspaceIdeSession).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Toggle workspace" }));

    await waitFor(() => {
      expect(createWorkspaceIdeSession).toHaveBeenCalledTimes(1);
    });
    const frame = screen.getByTitle("Workspace IDE");
    expect(frame).toHaveAttribute(
      "src",
      "/api/v1/workspace/ide/?folder=/workspace"
    );
    fireEvent.load(frame);

    await userEvent.click(screen.getByRole("button", { name: "Toggle workspace" }));
    await userEvent.click(screen.getByRole("button", { name: "Toggle workspace" }));

    expect(createWorkspaceIdeSession).toHaveBeenCalledTimes(1);
    expect(screen.getByTitle("Workspace IDE")).toHaveAttribute(
      "src",
      "/api/v1/workspace/ide/?folder=/workspace"
    );
  });
});

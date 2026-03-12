import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const mockUseAuth = vi.fn();

vi.mock("./features/auth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("./components/Sidebar", () => ({
  Sidebar: () => <aside>Sidebar</aside>,
}));

vi.mock("./pages/HomePage", () => ({
  HomePage: () => <div>Agent Workspace</div>,
}));

describe("App", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps the standard padded app shell on the agent route", async () => {
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      session: {
        user: { id: "user-1", name: "Alice", is_admin: false },
        session_id: "session-1",
        is_admin_impersonation: false,
      },
      logout: vi.fn(),
      login: vi.fn(),
      adoptLoginResponse: vi.fn(),
      refreshSession: vi.fn(),
    });

    const { container } = render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    await screen.findByText("Agent Workspace");

    expect(container.querySelector(".app-main")).toHaveClass("app-main-padded");
    expect(container.querySelector(".app-content")).not.toBeNull();
  });
});

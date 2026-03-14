import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Sidebar } from "./Sidebar";

const mockUseAuth = vi.fn();

vi.mock("../features/auth", () => ({
  AuthSessionCard: ({ collapsed = false }: { collapsed?: boolean }) => (
    <div data-collapsed={collapsed ? "true" : "false"} data-testid="auth-session-card">
      Session Card
    </div>
  ),
  useAuth: () => mockUseAuth(),
}));

describe("Sidebar", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the admin button above the session card for admin users", () => {
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      session: {
        user: { id: "admin-1", name: "admin", is_admin: true },
      },
    });

    const { container } = render(
      <MemoryRouter>
        <Sidebar collapsed={false} width={224} onToggle={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.queryByText("Local-first ledger with AI review")).not.toBeInTheDocument();
    const workspaceLink = screen.getByRole("link", { name: "Workspace" });
    expect(workspaceLink).toHaveAttribute("href", "/workspace");
    const adminLink = screen.getByRole("link", { name: "Admin" });
    expect(adminLink).toHaveAttribute("href", "/admin");
    expect(screen.getByTestId("auth-session-card")).toBeInTheDocument();

    const footer = container.querySelector(".sidebar-footer");
    expect(footer).not.toBeNull();
    const settingsLink = screen.getByRole("link", { name: "Settings" });
    expect(footer?.children[0]).toContainElement(settingsLink);
    expect(footer?.children[1]).toContainElement(adminLink);
    expect(footer?.children[2]).toHaveAttribute("data-testid", "auth-session-card");
  });

  it("does not render the admin button for non-admin users", () => {
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      session: {
        user: { id: "user-1", name: "alice", is_admin: false },
      },
    });

    const { container } = render(
      <MemoryRouter>
        <Sidebar collapsed={false} width={224} onToggle={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Workspace" })).toHaveAttribute("href", "/workspace");
    expect(screen.getByTestId("auth-session-card")).toBeInTheDocument();

    const footer = container.querySelector(".sidebar-footer");
    expect(footer).not.toBeNull();
    const settingsLink = screen.getByRole("link", { name: "Settings" });
    expect(footer?.children[0]).toContainElement(settingsLink);
    expect(footer?.children[1]).toHaveAttribute("data-testid", "auth-session-card");
  });

  it("passes the collapsed state through to the auth session card", () => {
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      session: {
        user: { id: "user-2", name: "casey", is_admin: false },
      },
    });

    render(
      <MemoryRouter>
        <Sidebar collapsed width={224} onToggle={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.getByTestId("auth-session-card")).toHaveAttribute("data-collapsed", "true");
  });

  it("renders filters directly below groups in the sidebar nav", () => {
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      session: {
        user: { id: "user-3", name: "casey", is_admin: false },
      },
    });

    render(
      <MemoryRouter>
        <Sidebar collapsed={false} width={224} onToggle={vi.fn()} />
      </MemoryRouter>
    );

    const navLinks = screen
      .getAllByRole("link")
      .map((link) => link.textContent)
      .filter((label): label is string => Boolean(label));

    expect(navLinks).toEqual([
      "Agent",
      "Workspace",
      "Dashboard",
      "Accounts",
      "Entries",
      "Groups",
      "Filters",
      "Entities",
      "Properties",
      "Settings",
    ]);
  });
});

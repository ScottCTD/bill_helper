import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthSessionCard } from "./AuthSessionCard";

const mockUseAuth = vi.fn();

vi.mock("./AuthProvider", () => ({
  useAuth: () => mockUseAuth(),
}));

describe("AuthSessionCard", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders admin session controls and logout", async () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      session: {
        user: { id: "admin-1", name: "admin", is_admin: true },
        session_id: "session-1",
        is_admin_impersonation: false,
      },
      logout,
    });

    render(
      <MemoryRouter>
        <AuthSessionCard />
      </MemoryRouter>
    );

    expect(screen.getByText("Signed In")).toBeInTheDocument();
    expect(screen.getByText("admin (admin)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Admin" })).toHaveAttribute("href", "/admin");

    await userEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("renders impersonation label without the admin link for non-admin sessions", () => {
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      session: {
        user: { id: "user-1", name: "alice", is_admin: false },
        session_id: "session-2",
        is_admin_impersonation: true,
      },
      logout: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AuthSessionCard />
      </MemoryRouter>
    );

    expect(screen.getByText("alice (impersonating)")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });
});

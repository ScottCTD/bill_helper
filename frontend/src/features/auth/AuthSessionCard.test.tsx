import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("renders a sidebar logout item with the username", async () => {
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

    render(<AuthSessionCard />);

    expect(screen.getByRole("button", { name: "Logout (admin)" })).toBeInTheDocument();
    expect(screen.queryByText("Signed In")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Logout (admin)" }));
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("does not append impersonation or admin labels to the logout item label", () => {
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      session: {
        user: { id: "user-1", name: "alice", is_admin: false },
        session_id: "session-2",
        is_admin_impersonation: true,
      },
      logout: vi.fn(),
    });

    render(<AuthSessionCard />);

    expect(screen.getByRole("button", { name: "Logout (alice)" })).toBeInTheDocument();
    expect(screen.queryByText(/impersonating/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });

  it("renders an icon-only logout item in collapsed mode", async () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      session: {
        user: { id: "user-2", name: "casey", is_admin: false },
        session_id: "session-3",
        is_admin_impersonation: false,
      },
      logout,
    });

    render(<AuthSessionCard collapsed />);

    expect(screen.queryByText("Logout (casey)")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Logout (casey)" })).toHaveClass("sidebar-link");

    await userEvent.click(screen.getByRole("button", { name: "Logout (casey)" }));
    expect(logout).toHaveBeenCalledTimes(1);
  });
});

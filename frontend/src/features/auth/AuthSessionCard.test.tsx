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

  it("renders only the account name and logout action", async () => {
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

    expect(screen.getByText("admin")).toBeInTheDocument();
    expect(screen.queryByText("Signed In")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("does not append impersonation or admin labels to the account name", () => {
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

    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.queryByText(/impersonating/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";

const mockUseAuth = vi.fn();
const mockNavigate = vi.fn();

vi.mock("../features/auth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({ state: { from: { pathname: "/accounts" } } }),
  };
});

describe("LoginPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("submits username and password through the auth context", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue({
      status: "unauthenticated",
      login,
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText("User name"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith({ username: "admin", password: "secret" });
    });
    expect(mockNavigate).toHaveBeenCalledWith("/accounts", { replace: true });
  });

  it("renders login errors from the auth context", async () => {
    const login = vi.fn().mockRejectedValue(new Error("Invalid username or password."));
    mockUseAuth.mockReturnValue({
      status: "unauthenticated",
      login,
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText("User name"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Invalid username or password.")).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});

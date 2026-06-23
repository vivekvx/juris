import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { LoginCard } from "../login-card";

const mockSignIn = vi.fn();
const mockSignInWithGoogle = vi.fn();

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    signIn: mockSignIn,
    signInWithGoogle: mockSignInWithGoogle,
    user: null,
    loading: false,
    isAuthenticated: false,
    signUp: vi.fn(),
    signOut: vi.fn(),
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("LoginCard", () => {
  it("renders email and password fields", () => {
    render(<LoginCard />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("renders Google sign-in button", () => {
    render(<LoginCard />);
    expect(screen.getByText("Continue with Google")).toBeInTheDocument();
  });

  it("submit button disabled when fields empty", () => {
    render(<LoginCard />);
    expect(screen.getByRole("button", { name: /sign in/i })).toBeDisabled();
  });

  it("submit button enabled when fields filled", () => {
    render(<LoginCard />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret" } });
    expect(screen.getByRole("button", { name: /sign in/i })).not.toBeDisabled();
  });

  it("calls signIn on submit", async () => {
    mockSignIn.mockResolvedValue(undefined);
    render(<LoginCard />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret" } });
    fireEvent.submit(screen.getByLabelText(/email/i).closest("form")!);
    await waitFor(() =>
      expect(mockSignIn).toHaveBeenCalledWith("a@b.com", "secret")
    );
  });

  it("shows error message on auth failure", async () => {
    mockSignIn.mockRejectedValue(new Error("Incorrect email or password."));
    render(<LoginCard />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "wrong" } });
    fireEvent.submit(screen.getByLabelText(/email/i).closest("form")!);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Incorrect email or password.")
    );
  });

  it("calls signInWithGoogle on Google button click", async () => {
    mockSignInWithGoogle.mockResolvedValue(undefined);
    render(<LoginCard />);
    fireEvent.click(screen.getByText("Continue with Google"));
    await waitFor(() => expect(mockSignInWithGoogle).toHaveBeenCalledOnce());
  });

  it("links to signup page", () => {
    render(<LoginCard />);
    expect(screen.getByRole("link", { name: /create one/i })).toHaveAttribute(
      "href",
      "/auth/signup"
    );
  });
});

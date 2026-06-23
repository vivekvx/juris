import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { SignupCard } from "../signup-card";

const mockSignUp = vi.fn();
const mockSignInWithGoogle = vi.fn();

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    signUp: mockSignUp,
    signInWithGoogle: mockSignInWithGoogle,
    user: null,
    loading: false,
    isAuthenticated: false,
    signIn: vi.fn(),
    signOut: vi.fn(),
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SignupCard", () => {
  it("renders name, email, and password fields", () => {
    render(<SignupCard />);
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("renders Google sign-up button", () => {
    render(<SignupCard />);
    expect(screen.getByText("Continue with Google")).toBeInTheDocument();
  });

  it("submit button disabled when required fields empty", () => {
    render(<SignupCard />);
    expect(screen.getByRole("button", { name: /create account/i })).toBeDisabled();
  });

  it("submit button enabled when email and password filled", () => {
    render(<SignupCard />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret123" } });
    expect(screen.getByRole("button", { name: /create account/i })).not.toBeDisabled();
  });

  it("calls signUp on submit", async () => {
    mockSignUp.mockResolvedValue(undefined);
    render(<SignupCard />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret123" } });
    fireEvent.submit(screen.getByLabelText(/email/i).closest("form")!);
    await waitFor(() =>
      expect(mockSignUp).toHaveBeenCalledWith("a@b.com", "secret123", "")
    );
  });

  it("passes name to signUp when provided", async () => {
    mockSignUp.mockResolvedValue(undefined);
    render(<SignupCard />);
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Priya Sharma" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret123" } });
    fireEvent.submit(screen.getByLabelText(/email/i).closest("form")!);
    await waitFor(() =>
      expect(mockSignUp).toHaveBeenCalledWith("a@b.com", "secret123", "Priya Sharma")
    );
  });

  it("shows error on signup failure", async () => {
    mockSignUp.mockRejectedValue(new Error("An account with this email already exists."));
    render(<SignupCard />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret123" } });
    fireEvent.submit(screen.getByLabelText(/email/i).closest("form")!);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "An account with this email already exists."
      )
    );
  });

  it("links to login page", () => {
    render(<SignupCard />);
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute(
      "href",
      "/auth/login"
    );
  });
});

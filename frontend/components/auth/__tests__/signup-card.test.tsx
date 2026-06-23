import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { SignupCard } from "../signup-card";

vi.mock("@/lib/firebase", () => ({ getAuth: vi.fn(() => ({})) }));
vi.mock("firebase/auth", () => ({
  createUserWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  GoogleAuthProvider: class {},
  updateProfile: vi.fn(),
}));

import * as firebaseAuth from "firebase/auth";

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

  it("calls createUserWithEmailAndPassword on submit", async () => {
    vi.mocked(firebaseAuth.createUserWithEmailAndPassword).mockResolvedValue({
      user: { displayName: null },
    } as never);
    render(<SignupCard />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret123" } });
    fireEvent.submit(screen.getByLabelText(/email/i).closest("form")!);
    await waitFor(() =>
      expect(firebaseAuth.createUserWithEmailAndPassword).toHaveBeenCalledWith(
        {},
        "a@b.com",
        "secret123"
      )
    );
  });

  it("calls updateProfile when name is provided", async () => {
    vi.mocked(firebaseAuth.createUserWithEmailAndPassword).mockResolvedValue({
      user: { displayName: null },
    } as never);
    vi.mocked(firebaseAuth.updateProfile).mockResolvedValue(undefined);
    render(<SignupCard />);
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Priya Sharma" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret123" } });
    fireEvent.submit(screen.getByLabelText(/email/i).closest("form")!);
    await waitFor(() =>
      expect(firebaseAuth.updateProfile).toHaveBeenCalledWith(
        expect.anything(),
        { displayName: "Priya Sharma" }
      )
    );
  });

  it("shows error on email already in use", async () => {
    const err = Object.assign(new Error(), { code: "auth/email-already-in-use" });
    vi.mocked(firebaseAuth.createUserWithEmailAndPassword).mockRejectedValue(err);
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

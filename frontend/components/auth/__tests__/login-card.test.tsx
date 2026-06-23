import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { LoginCard } from "../login-card";

vi.mock("@/lib/firebase", () => ({ getAuth: vi.fn(() => ({})) }));
vi.mock("firebase/auth", () => ({
  signInWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  // Arrow functions cannot be used as constructors; use class to allow `new`
  GoogleAuthProvider: class {},
}));

import * as firebaseAuth from "firebase/auth";

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

  it("calls signInWithEmailAndPassword on submit", async () => {
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockResolvedValue({} as never);
    render(<LoginCard />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret" } });
    fireEvent.submit(screen.getByLabelText(/email/i).closest("form")!);
    await waitFor(() =>
      expect(firebaseAuth.signInWithEmailAndPassword).toHaveBeenCalledWith({}, "a@b.com", "secret")
    );
  });

  it("shows error message on auth failure", async () => {
    const err = Object.assign(new Error(), { code: "auth/invalid-credential" });
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockRejectedValue(err);
    render(<LoginCard />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "wrong" } });
    fireEvent.submit(screen.getByLabelText(/email/i).closest("form")!);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Incorrect email or password.")
    );
  });

  it("calls signInWithPopup on Google button click", async () => {
    vi.mocked(firebaseAuth.signInWithPopup).mockResolvedValue({} as never);
    render(<LoginCard />);
    fireEvent.click(screen.getByText("Continue with Google"));
    await waitFor(() => expect(firebaseAuth.signInWithPopup).toHaveBeenCalledOnce());
  });

  it("links to signup page", () => {
    render(<LoginCard />);
    expect(screen.getByRole("link", { name: /create one/i })).toHaveAttribute(
      "href",
      "/auth/signup"
    );
  });
});

import { render, screen, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { AuthProvider } from "../auth-provider";
import { useAuth } from "@/hooks/use-auth";

vi.mock("@/lib/firebase", () => ({ getAuth: vi.fn(() => ({})) }));

let onAuthStateChangedCallback: ((user: unknown) => void) | null = null;
const mockUnsubscribe = vi.fn();

vi.mock("firebase/auth", () => ({
  onAuthStateChanged: vi.fn((_auth: unknown, cb: (user: unknown) => void) => {
    onAuthStateChangedCallback = cb;
    return mockUnsubscribe;
  }),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  signOut: vi.fn(),
  updateProfile: vi.fn(),
  GoogleAuthProvider: class {},
}));

import * as firebaseAuth from "firebase/auth";

function Consumer() {
  const auth = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(auth.loading)}</span>
      <span data-testid="authenticated">{String(auth.isAuthenticated)}</span>
      <span data-testid="uid">{auth.user?.uid ?? "null"}</span>
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  onAuthStateChangedCallback = null;
});

describe("AuthProvider", () => {
  it("starts in loading state", () => {
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );
    expect(screen.getByTestId("loading").textContent).toBe("true");
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
  });

  it("resolves loading after auth restored (null user)", async () => {
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );
    act(() => onAuthStateChangedCallback!(null));
    await waitFor(() =>
      expect(screen.getByTestId("loading").textContent).toBe("false")
    );
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
  });

  it("sets user after auth restoration with signed-in user", async () => {
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );
    act(() =>
      onAuthStateChangedCallback!({
        uid: "u1",
        email: "a@b.com",
        displayName: "Test",
        photoURL: null,
      })
    );
    await waitFor(() =>
      expect(screen.getByTestId("uid").textContent).toBe("u1")
    );
    expect(screen.getByTestId("authenticated").textContent).toBe("true");
  });

  it("cleans up subscription on unmount", () => {
    const { unmount } = render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );
    unmount();
    expect(mockUnsubscribe).toHaveBeenCalledOnce();
  });

  it("signIn calls signInWithEmailAndPassword", async () => {
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockResolvedValue({} as never);
    let authCtx: ReturnType<typeof useAuth> | null = null;
    function Capture() {
      authCtx = useAuth();
      return null;
    }
    render(
      <AuthProvider>
        <Capture />
      </AuthProvider>
    );
    await act(() => authCtx!.signIn("a@b.com", "pass"));
    expect(firebaseAuth.signInWithEmailAndPassword).toHaveBeenCalledWith({}, "a@b.com", "pass");
  });

  it("signIn throws human error on failure", async () => {
    const err = Object.assign(new Error(), { code: "auth/invalid-credential" });
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockRejectedValue(err);
    let authCtx: ReturnType<typeof useAuth> | null = null;
    function Capture() {
      authCtx = useAuth();
      return null;
    }
    render(
      <AuthProvider>
        <Capture />
      </AuthProvider>
    );
    await expect(authCtx!.signIn("a@b.com", "bad")).rejects.toThrow(
      "Incorrect email or password."
    );
  });

  it("signUp calls createUserWithEmailAndPassword", async () => {
    vi.mocked(firebaseAuth.createUserWithEmailAndPassword).mockResolvedValue({
      user: { displayName: null },
    } as never);
    let authCtx: ReturnType<typeof useAuth> | null = null;
    function Capture() {
      authCtx = useAuth();
      return null;
    }
    render(
      <AuthProvider>
        <Capture />
      </AuthProvider>
    );
    await act(() => authCtx!.signUp("a@b.com", "pass"));
    expect(firebaseAuth.createUserWithEmailAndPassword).toHaveBeenCalledWith(
      {},
      "a@b.com",
      "pass"
    );
  });

  it("signUp calls updateProfile when displayName provided", async () => {
    vi.mocked(firebaseAuth.createUserWithEmailAndPassword).mockResolvedValue({
      user: {},
    } as never);
    vi.mocked(firebaseAuth.updateProfile).mockResolvedValue(undefined);
    let authCtx: ReturnType<typeof useAuth> | null = null;
    function Capture() {
      authCtx = useAuth();
      return null;
    }
    render(
      <AuthProvider>
        <Capture />
      </AuthProvider>
    );
    await act(() => authCtx!.signUp("a@b.com", "pass", "Priya"));
    expect(firebaseAuth.updateProfile).toHaveBeenCalledWith(
      expect.anything(),
      { displayName: "Priya" }
    );
  });

  it("signOut calls firebase signOut", async () => {
    vi.mocked(firebaseAuth.signOut).mockResolvedValue(undefined);
    let authCtx: ReturnType<typeof useAuth> | null = null;
    function Capture() {
      authCtx = useAuth();
      return null;
    }
    render(
      <AuthProvider>
        <Capture />
      </AuthProvider>
    );
    await act(() => authCtx!.signOut());
    expect(firebaseAuth.signOut).toHaveBeenCalledOnce();
  });

  it("signInWithGoogle calls signInWithPopup", async () => {
    vi.mocked(firebaseAuth.signInWithPopup).mockResolvedValue({} as never);
    let authCtx: ReturnType<typeof useAuth> | null = null;
    function Capture() {
      authCtx = useAuth();
      return null;
    }
    render(
      <AuthProvider>
        <Capture />
      </AuthProvider>
    );
    await act(() => authCtx!.signInWithGoogle());
    expect(firebaseAuth.signInWithPopup).toHaveBeenCalledOnce();
  });
});

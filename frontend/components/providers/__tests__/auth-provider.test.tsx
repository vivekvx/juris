import { render, screen, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { AuthProvider } from "../auth-provider";
import { useAuth } from "@/hooks/use-auth";

vi.mock("@/lib/firebase", () => ({ getAuth: vi.fn(() => ({})) }));

let onAuthStateChangedCallback: ((user: unknown) => void) | null = null;
const mockUnsubscribe = vi.fn();

const mockUser = { getIdToken: vi.fn(() => Promise.resolve("mock-id-token")) };

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

const mockFetch = vi.fn(() =>
  Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) })
);

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

function Capture({ capture }: { capture: (ctx: ReturnType<typeof useAuth>) => void }) {
  capture(useAuth());
  return null;
}

beforeEach(() => {
  vi.clearAllMocks();
  onAuthStateChangedCallback = null;
  vi.stubGlobal("fetch", mockFetch);
});

describe("AuthProvider", () => {
  it("starts in loading state", () => {
    render(<AuthProvider><Consumer /></AuthProvider>);
    expect(screen.getByTestId("loading").textContent).toBe("true");
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
  });

  it("resolves loading after auth restored (null user)", async () => {
    render(<AuthProvider><Consumer /></AuthProvider>);
    act(() => onAuthStateChangedCallback!(null));
    await waitFor(() =>
      expect(screen.getByTestId("loading").textContent).toBe("false")
    );
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
  });

  it("sets user after auth restoration with signed-in user", async () => {
    render(<AuthProvider><Consumer /></AuthProvider>);
    act(() =>
      onAuthStateChangedCallback!({ uid: "u1", email: "a@b.com", displayName: "Test", photoURL: null })
    );
    await waitFor(() => expect(screen.getByTestId("uid").textContent).toBe("u1"));
    expect(screen.getByTestId("authenticated").textContent).toBe("true");
  });

  it("cleans up subscription on unmount", () => {
    const { unmount } = render(<AuthProvider><Consumer /></AuthProvider>);
    unmount();
    expect(mockUnsubscribe).toHaveBeenCalledOnce();
  });

  it("signIn calls signInWithEmailAndPassword and creates session", async () => {
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockResolvedValue({ user: mockUser } as never);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signIn("a@b.com", "pass"));
    expect(firebaseAuth.signInWithEmailAndPassword).toHaveBeenCalledWith({}, "a@b.com", "pass");
    expect(mockFetch).toHaveBeenCalledWith("/api/auth/session", expect.objectContaining({ method: "POST" }));
  });

  it("signIn throws human error on Firebase failure", async () => {
    const err = Object.assign(new Error(), { code: "auth/invalid-credential" });
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockRejectedValue(err);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await expect(ctx!.signIn("a@b.com", "bad")).rejects.toThrow("Incorrect email or password.");
  });

  it("signIn rolls back and throws when session creation fails", async () => {
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockResolvedValue({ user: mockUser } as never);
    vi.mocked(firebaseAuth.signOut).mockResolvedValue(undefined);
    mockFetch.mockResolvedValueOnce({ ok: false } as never);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await expect(ctx!.signIn("a@b.com", "pass")).rejects.toThrow("secure session");
    expect(firebaseAuth.signOut).toHaveBeenCalledOnce();
  });

  it("signUp calls createUserWithEmailAndPassword and creates session", async () => {
    vi.mocked(firebaseAuth.createUserWithEmailAndPassword).mockResolvedValue({ user: mockUser } as never);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signUp("a@b.com", "pass"));
    expect(firebaseAuth.createUserWithEmailAndPassword).toHaveBeenCalledWith({}, "a@b.com", "pass");
    expect(mockFetch).toHaveBeenCalledWith("/api/auth/session", expect.objectContaining({ method: "POST" }));
  });

  it("signUp calls updateProfile when displayName provided", async () => {
    const userWithProfile = { ...mockUser };
    vi.mocked(firebaseAuth.createUserWithEmailAndPassword).mockResolvedValue({ user: userWithProfile } as never);
    vi.mocked(firebaseAuth.updateProfile).mockResolvedValue(undefined);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signUp("a@b.com", "pass", "Priya"));
    expect(firebaseAuth.updateProfile).toHaveBeenCalledWith(expect.anything(), { displayName: "Priya" });
  });

  it("signOut calls firebaseSignOut then DELETE session cookie", async () => {
    vi.mocked(firebaseAuth.signOut).mockResolvedValue(undefined);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signOut());
    expect(firebaseAuth.signOut).toHaveBeenCalledOnce();
    expect(mockFetch).toHaveBeenCalledWith("/api/auth/session", expect.objectContaining({ method: "DELETE" }));
    // Verify order: Firebase signOut before DELETE fetch
    const fetchCall = mockFetch.mock.invocationCallOrder[0];
    const signOutCall = vi.mocked(firebaseAuth.signOut).mock.invocationCallOrder[0];
    expect(signOutCall).toBeLessThan(fetchCall);
  });

  it("signInWithGoogle calls signInWithPopup and creates session", async () => {
    vi.mocked(firebaseAuth.signInWithPopup).mockResolvedValue({ user: mockUser } as never);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signInWithGoogle());
    expect(firebaseAuth.signInWithPopup).toHaveBeenCalledOnce();
    expect(mockFetch).toHaveBeenCalledWith("/api/auth/session", expect.objectContaining({ method: "POST" }));
  });
});

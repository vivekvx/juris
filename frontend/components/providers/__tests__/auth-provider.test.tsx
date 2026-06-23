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

// Two fetch targets per sign-in: /api/auth/session + backend /api/users/me
const SESSION_URL = "/api/auth/session";
const PROFILE_URL = "http://localhost:8001/api/users/me";

const mockFetch = vi.fn();

function okResponse() {
  return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) });
}


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
  // Default: both calls succeed
  mockFetch.mockImplementation(() => okResponse());
  vi.stubGlobal("fetch", mockFetch);
});

// ---------------------------------------------------------------------------
// Auth state restoration
// ---------------------------------------------------------------------------

describe("auth restoration", () => {
  it("starts in loading state", () => {
    render(<AuthProvider><Consumer /></AuthProvider>);
    expect(screen.getByTestId("loading").textContent).toBe("true");
  });

  it("resolves loading with null user after no session", async () => {
    render(<AuthProvider><Consumer /></AuthProvider>);
    act(() => onAuthStateChangedCallback!(null));
    await waitFor(() =>
      expect(screen.getByTestId("loading").textContent).toBe("false")
    );
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
  });

  it("restores authenticated user from Firebase cache", async () => {
    render(<AuthProvider><Consumer /></AuthProvider>);
    act(() =>
      onAuthStateChangedCallback!({ uid: "u1", email: "a@b.com", displayName: "A", photoURL: null })
    );
    await waitFor(() => expect(screen.getByTestId("uid").textContent).toBe("u1"));
    // Restoration does NOT call the session or profile APIs — no fetch
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("cleanup: unsubscribes onAuthStateChanged on unmount", () => {
    const { unmount } = render(<AuthProvider><Consumer /></AuthProvider>);
    unmount();
    expect(mockUnsubscribe).toHaveBeenCalledOnce();
  });
});

// ---------------------------------------------------------------------------
// signIn — four-step flow
// ---------------------------------------------------------------------------

describe("signIn", () => {
  it("calls signInWithEmailAndPassword", async () => {
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockResolvedValue({ user: mockUser } as never);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signIn("a@b.com", "pass"));
    expect(firebaseAuth.signInWithEmailAndPassword).toHaveBeenCalledWith({}, "a@b.com", "pass");
  });

  it("creates server-side session cookie", async () => {
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockResolvedValue({ user: mockUser } as never);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signIn("a@b.com", "pass"));
    expect(mockFetch).toHaveBeenCalledWith(SESSION_URL, expect.objectContaining({ method: "POST" }));
  });

  it("initializes backend profile after session creation", async () => {
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockResolvedValue({ user: mockUser } as never);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signIn("a@b.com", "pass"));
    expect(mockFetch).toHaveBeenCalledWith(
      PROFILE_URL,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer mock-id-token" }),
      })
    );
  });

  it("session created before profile (order)", async () => {
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockResolvedValue({ user: mockUser } as never);
    const calls: string[] = [];
    mockFetch.mockImplementation((url: string) => {
      calls.push(url as string);
      return okResponse();
    });
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signIn("a@b.com", "pass"));
    expect(calls[0]).toBe(SESSION_URL);
    expect(calls[1]).toBe(PROFILE_URL);
  });

  it("throws human error on Firebase failure", async () => {
    const err = Object.assign(new Error(), { code: "auth/invalid-credential" });
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockRejectedValue(err);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await expect(ctx!.signIn("a@b.com", "bad")).rejects.toThrow("Incorrect email or password.");
  });

  it("rolls back Firebase when session creation fails", async () => {
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockResolvedValue({ user: mockUser } as never);
    vi.mocked(firebaseAuth.signOut).mockResolvedValue(undefined);
    mockFetch.mockResolvedValueOnce({ ok: false } as never);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await expect(ctx!.signIn("a@b.com", "pass")).rejects.toThrow("secure session");
    expect(firebaseAuth.signOut).toHaveBeenCalledOnce();
  });

  it("rolls back Firebase and session when profile init fails", async () => {
    vi.mocked(firebaseAuth.signInWithEmailAndPassword).mockResolvedValue({ user: mockUser } as never);
    vi.mocked(firebaseAuth.signOut).mockResolvedValue(undefined);
    // Session succeeds, profile fails
    mockFetch
      .mockResolvedValueOnce({ ok: true } as never)
      .mockResolvedValueOnce({ ok: false } as never);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await expect(ctx!.signIn("a@b.com", "pass")).rejects.toThrow("initialize your profile");
    expect(firebaseAuth.signOut).toHaveBeenCalledOnce();
    expect(mockFetch).toHaveBeenCalledWith(SESSION_URL, expect.objectContaining({ method: "DELETE" }));
  });
});

// ---------------------------------------------------------------------------
// signUp
// ---------------------------------------------------------------------------

describe("signUp", () => {
  it("creates session and profile on signup", async () => {
    vi.mocked(firebaseAuth.createUserWithEmailAndPassword).mockResolvedValue({ user: mockUser } as never);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signUp("a@b.com", "pass"));
    expect(mockFetch).toHaveBeenCalledWith(SESSION_URL, expect.objectContaining({ method: "POST" }));
    expect(mockFetch).toHaveBeenCalledWith(PROFILE_URL, expect.anything());
  });

  it("calls updateProfile when displayName provided", async () => {
    const userWithProfile = { ...mockUser };
    vi.mocked(firebaseAuth.createUserWithEmailAndPassword).mockResolvedValue({ user: userWithProfile } as never);
    vi.mocked(firebaseAuth.updateProfile).mockResolvedValue(undefined);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signUp("a@b.com", "pass", "Priya"));
    expect(firebaseAuth.updateProfile).toHaveBeenCalledWith(expect.anything(), { displayName: "Priya" });
  });
});

// ---------------------------------------------------------------------------
// signInWithGoogle
// ---------------------------------------------------------------------------

describe("signInWithGoogle", () => {
  it("creates session and profile", async () => {
    vi.mocked(firebaseAuth.signInWithPopup).mockResolvedValue({ user: mockUser } as never);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signInWithGoogle());
    expect(mockFetch).toHaveBeenCalledWith(SESSION_URL, expect.objectContaining({ method: "POST" }));
    expect(mockFetch).toHaveBeenCalledWith(PROFILE_URL, expect.anything());
  });
});

// ---------------------------------------------------------------------------
// signOut — Firebase first, then DELETE cookie
// ---------------------------------------------------------------------------

describe("signOut", () => {
  it("calls firebaseSignOut then deletes session cookie", async () => {
    vi.mocked(firebaseAuth.signOut).mockResolvedValue(undefined);
    let ctx: ReturnType<typeof useAuth> | null = null;
    render(<AuthProvider><Capture capture={(c) => { ctx = c; }} /></AuthProvider>);
    await act(() => ctx!.signOut());
    expect(firebaseAuth.signOut).toHaveBeenCalledOnce();
    expect(mockFetch).toHaveBeenCalledWith(SESSION_URL, expect.objectContaining({ method: "DELETE" }));
    // Order: Firebase before DELETE
    const deleteCall = mockFetch.mock.invocationCallOrder[0];
    const signOutCall = vi.mocked(firebaseAuth.signOut).mock.invocationCallOrder[0];
    expect(signOutCall).toBeLessThan(deleteCall);
  });
});

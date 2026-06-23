import { renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import React from "react";
import { AuthContext, type AuthContextValue } from "@/components/providers/auth-provider";
import { useAuth } from "../use-auth";

describe("useAuth", () => {
  it("throws when used outside AuthProvider", () => {
    expect(() => renderHook(() => useAuth())).toThrow(
      "useAuth must be used within AuthProvider"
    );
  });

  it("returns context value when inside AuthProvider", () => {
    const value: AuthContextValue = {
      user: { uid: "u1", email: "a@b.com", displayName: "Test", photoURL: null },
      loading: false,
      isAuthenticated: true,
      signIn: async () => {},
      signUp: async () => {},
      signInWithGoogle: async () => {},
      signOut: async () => {},
    };
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
    );
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.user?.uid).toBe("u1");
    expect(result.current.isAuthenticated).toBe(true);
  });
});

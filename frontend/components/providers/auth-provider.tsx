"use client";
import { createContext, useEffect, useState, type ReactNode } from "react";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut as firebaseSignOut,
  updateProfile,
  GoogleAuthProvider,
  type User as FirebaseUser,
} from "firebase/auth";
import { getAuth } from "@/lib/firebase";
import { authErrorMessage } from "@/lib/auth-errors";
import { backendPost } from "@/lib/api";
import type { User } from "@/types/user";

export interface AuthContextValue {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, displayName?: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

function mapUser(u: FirebaseUser): User {
  return {
    uid: u.uid,
    email: u.email,
    displayName: u.displayName,
    photoURL: u.photoURL,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(getAuth(), (firebaseUser) => {
      setUser(firebaseUser ? mapUser(firebaseUser) : null);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  async function createSession(user: FirebaseUser): Promise<void> {
    const idToken = await user.getIdToken();

    const sessionRes = await fetch("/api/auth/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken }),
    });
    if (!sessionRes.ok) {
      await firebaseSignOut(getAuth());
      throw new Error(
        "Signed in successfully, but we couldn't establish a secure session. Please try again."
      );
    }

    const profileRes = await backendPost("/api/users/me", idToken);
    if (!profileRes.ok) {
      await firebaseSignOut(getAuth());
      await fetch("/api/auth/session", { method: "DELETE" });
      throw new Error(
        "Signed in successfully, but we couldn't initialize your profile. Please try again."
      );
    }
  }

  async function signIn(email: string, password: string): Promise<void> {
    try {
      const credential = await signInWithEmailAndPassword(getAuth(), email, password);
      await createSession(credential.user);
    } catch (err) {
      if (err instanceof Error && (err.message.includes("secure session") || err.message.includes("initialize your profile"))) throw err;
      throw new Error(authErrorMessage(err));
    }
  }

  async function signUp(email: string, password: string, displayName?: string): Promise<void> {
    try {
      const credential = await createUserWithEmailAndPassword(getAuth(), email, password);
      if (displayName?.trim()) {
        await updateProfile(credential.user, { displayName: displayName.trim() });
      }
      await createSession(credential.user);
    } catch (err) {
      if (err instanceof Error && (err.message.includes("secure session") || err.message.includes("initialize your profile"))) throw err;
      throw new Error(authErrorMessage(err));
    }
  }

  async function signInWithGoogle(): Promise<void> {
    try {
      const credential = await signInWithPopup(getAuth(), new GoogleAuthProvider());
      await createSession(credential.user);
    } catch (err) {
      if (err instanceof Error && (err.message.includes("secure session") || err.message.includes("initialize your profile"))) throw err;
      throw new Error(authErrorMessage(err));
    }
  }

  async function signOut(): Promise<void> {
    try {
      await firebaseSignOut(getAuth());
      await fetch("/api/auth/session", { method: "DELETE" });
    } catch (err) {
      throw new Error(authErrorMessage(err));
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: user !== null,
        signIn,
        signUp,
        signInWithGoogle,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

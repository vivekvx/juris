import { getSession } from "@/lib/session";
import type { User } from "@/types/user";

export async function getCurrentUser(): Promise<User | null> {
  const session = await getSession();
  if (!session) return null;
  return {
    uid: session.uid,
    email: session.email ?? null,
    displayName: session.name ?? null,
    photoURL: session.picture ?? null,
  };
}

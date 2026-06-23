import { cookies } from "next/headers";
import type { DecodedIdToken } from "firebase-admin/auth";
import { getAdminAuth } from "@/lib/firebase-admin";

export async function getSession(): Promise<DecodedIdToken | null> {
  try {
    const cookieStore = await cookies();
    const session = cookieStore.get("__session")?.value;
    if (!session) return null;
    return await getAdminAuth().verifySessionCookie(session, true);
  } catch {
    return null;
  }
}

import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/current-user";
import type { ReactNode } from "react";

export default async function ProtectedLayout({ children }: { children: ReactNode }) {
  const user = await getCurrentUser();
  if (!user) redirect("/auth/login");
  return <>{children}</>;
}

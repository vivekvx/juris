"use client";
import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Trash } from "@phosphor-icons/react";
import { toast } from "sonner";
import { getAuth } from "@/lib/firebase";
import { deleteConversation } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useConversations } from "@/hooks/use-conversations";

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(
    new Date(iso),
  );
}

export function SidebarConversations() {
  const pathname = usePathname();
  const { state, load } = useConversations();

  useEffect(() => { void load(); }, [pathname, load]);

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    try {
      const currentUser = getAuth().currentUser;
      if (!currentUser) return;
      const idToken = await currentUser.getIdToken();
      await deleteConversation(id, idToken);
      void load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete conversation.");
    }
  }

  const conversations =
    state.status === "ready" ? state.conversations : [];

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-y-auto">
      {conversations.length > 0 && (
        <>
          <div className="px-4 pt-3 pb-1">
            <p className="text-[0.625rem] font-medium text-muted-foreground/60 uppercase tracking-widest">
              Recent
            </p>
          </div>
          <nav className="flex flex-col gap-px px-2 pb-2">
            {conversations.map((conv) => {
              const active = pathname === `/workspace/${conv.id}`;
              const timestamp = conv.last_message_at ?? conv.created_at;
              return (
                <Link
                  key={conv.id}
                  href={`/workspace/${conv.id}`}
                  className={cn(
                    "group flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors min-w-0",
                    "hover:bg-secondary",
                    active
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  <span className="flex-1 truncate text-[0.8125rem] min-w-0">
                    {conv.title}
                  </span>
                  <span className="flex-shrink-0 text-[0.625rem] text-muted-foreground/50 group-hover:hidden">
                    {formatRelative(timestamp)}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => void handleDelete(conv.id, e)}
                    className={cn(
                      "hidden group-hover:flex flex-shrink-0 items-center justify-center",
                      "rounded p-0.5 hover:text-destructive transition-colors",
                    )}
                    aria-label={`Delete "${conv.title}"`}
                  >
                    <Trash size={12} />
                  </button>
                </Link>
              );
            })}
          </nav>
        </>
      )}
    </div>
  );
}

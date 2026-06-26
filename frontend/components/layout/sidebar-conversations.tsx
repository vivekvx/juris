"use client";
import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Trash, ChatCircle } from "@phosphor-icons/react";
import { toast } from "sonner";
import { getAuth } from "@/lib/firebase";
import { deleteConversation } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
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

function ConversationSkeletons() {
  return (
    <div className="flex flex-col gap-px px-2 pb-2" aria-hidden>
      {[72, 55, 80, 48].map((w) => (
        <div key={w} className="flex items-center gap-2 px-2 py-1.5">
          <Skeleton className="h-3 rounded" style={{ width: `${w}%` }} />
          <Skeleton className="h-3 w-5 rounded ml-auto flex-shrink-0" />
        </div>
      ))}
    </div>
  );
}

function EmptyConversations() {
  return (
    <div className="flex flex-col items-center gap-2 px-3 py-6 text-center">
      <ChatCircle size={20} className="text-muted-foreground/30" weight="thin" />
      <p className="text-[0.75rem] text-muted-foreground/50 leading-snug">
        No conversations yet
      </p>
    </div>
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

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-y-auto">
      <div className="px-3 pt-4 pb-1.5">
        <p className="text-label text-muted-foreground/50">Recent</p>
      </div>

      {state.status === "loading" && <ConversationSkeletons />}

      {state.status === "ready" && state.conversations.length === 0 && (
        <EmptyConversations />
      )}

      {state.status === "ready" && state.conversations.length > 0 && (
        <nav className="flex flex-col gap-px px-2 pb-2" aria-label="Recent conversations">
          {state.conversations.map((conv) => {
            const active = pathname === `/workspace/${conv.id}`;
            const timestamp = conv.last_message_at ?? conv.created_at;
            return (
              <Link
                key={conv.id}
                href={`/workspace/${conv.id}`}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors min-w-0",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  active
                    ? "bg-primary/10 text-foreground"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                )}
              >
                <span className="flex-1 truncate text-[0.8125rem] min-w-0 leading-none">
                  {conv.title}
                </span>
                <span className="flex-shrink-0 text-[0.625rem] text-muted-foreground/40 group-hover:hidden tabular-nums">
                  {formatRelative(timestamp)}
                </span>
                <button
                  type="button"
                  onClick={(e) => void handleDelete(conv.id, e)}
                  className={cn(
                    "hidden group-hover:flex flex-shrink-0 items-center justify-center",
                    "h-5 w-5 rounded transition-colors",
                    "hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  )}
                  aria-label={`Delete "${conv.title}"`}
                >
                  <Trash size={11} />
                </button>
              </Link>
            );
          })}
        </nav>
      )}

      {state.status === "error" && (
        <p className="px-3 py-2 text-[0.75rem] text-muted-foreground/40">
          Could not load conversations.
        </p>
      )}
    </div>
  );
}

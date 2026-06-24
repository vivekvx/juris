import type { MessageResponse } from "@/types/conversation";
import { CitationCard } from "@/components/conversation/citation-card";

function formatTime(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function MessageBubble({
  message,
  streaming = false,
}: {
  message: MessageResponse;
  streaming?: boolean;
}) {
  const isUser = message.role === "user";
  const citations = message.citations ?? [];

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[75%] min-w-0">
        <div
          className={
            isUser
              ? "rounded-xl bg-primary/10 border border-primary/20 px-4 py-2.5"
              : "rounded-xl bg-card border border-border px-4 py-2.5"
          }
        >
          <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
            {message.content}
            {streaming && (
              <span className="inline-block w-1.5 h-3.5 ml-0.5 bg-foreground/60 animate-pulse rounded-sm align-middle" />
            )}
          </p>
        </div>

        {!isUser && citations.length > 0 && (
          <div className="mt-2 space-y-1">
            {citations.map((c, i) => (
              <CitationCard key={`${c.doc_id}-${c.chunk_index}`} citation={c} index={i + 1} />
            ))}
          </div>
        )}

        {!isUser && !streaming && citations.length === 0 && (
          <p className="text-[0.65rem] text-muted-foreground/40 mt-1 pl-1">
            No documents used
          </p>
        )}

        <p
          className={`text-[0.7rem] text-muted-foreground/60 mt-1 ${
            isUser ? "text-right pr-1" : "text-left pl-1"
          }`}
        >
          {!isUser && <span className="font-medium text-muted-foreground/80">Juris · </span>}
          {formatTime(message.created_at)}
        </p>
      </div>
    </div>
  );
}

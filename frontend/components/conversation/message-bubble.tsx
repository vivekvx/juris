import type { MessageResponse } from "@/types/conversation";

function formatTime(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function MessageBubble({ message }: { message: MessageResponse }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[75%]">
        <div
          className={
            isUser
              ? "rounded-xl bg-primary/10 border border-primary/20 px-4 py-2.5"
              : "rounded-xl bg-card border border-border px-4 py-2.5"
          }
        >
          <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
            {message.content}
          </p>
        </div>
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

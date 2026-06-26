"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { MessageResponse } from "@/types/conversation";
import { CitationCard } from "@/components/conversation/citation-card";
import { PlayButton } from "@/components/conversation/play-button";

function formatTime(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 py-1" aria-label="Juris is thinking">
      <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:-0.3s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:-0.15s]" />
      <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce" />
    </div>
  );
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
  const isEmpty = !message.content;

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] min-w-0">
          <div className="rounded-2xl bg-primary/10 border border-primary/15 px-4 py-3">
            <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
              {message.content}
            </p>
          </div>
          <p className="text-[0.68rem] text-muted-foreground/50 mt-1 text-right pr-1">
            {formatTime(message.created_at)}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="w-full min-w-0">
        {isEmpty && streaming ? (
          <ThinkingDots />
        ) : (
          <div className="prose-message">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
            {streaming && (
              <span
                aria-hidden
                className="inline-block w-0.5 h-[1.1em] ml-0.5 bg-foreground/60 align-text-bottom"
                style={{ animation: "blink 1s step-end infinite" }}
              />
            )}
          </div>
        )}

        {citations.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {citations.map((c, i) => (
              <CitationCard key={`${c.doc_id}-${c.chunk_index}`} citation={c} index={i + 1} />
            ))}
          </div>
        )}

        {!(isEmpty && streaming) && (
          <div className="flex items-center gap-1.5 mt-2">
            {!streaming && (
              <PlayButton messageId={message.id} text={message.content} />
            )}
            <p className="text-[0.68rem] text-muted-foreground/50">
              <span className="font-medium text-muted-foreground/60">Juris · </span>
              {formatTime(message.created_at)}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

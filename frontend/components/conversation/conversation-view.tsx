"use client";
import { useEffect, useRef } from "react";
import { Files } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { InputBar } from "@/components/conversation/input-bar";
import { MessageBubble } from "@/components/conversation/message-bubble";
import { useConversation } from "@/hooks/use-conversation";
import { useAutoPlay } from "@/hooks/use-auto-play";
import { useConversationStore } from "@/stores/conversation-store";

function MessageSkeletons() {
  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Skeleton className="h-10 w-48 rounded-xl" />
      </div>
      <div className="flex justify-start">
        <Skeleton className="h-16 w-64 rounded-xl" />
      </div>
      <div className="flex justify-end">
        <Skeleton className="h-10 w-36 rounded-xl" />
      </div>
    </div>
  );
}

export function ConversationView({ conversationId }: { conversationId: string }) {
  const { state, sending, send, streamingMessage, autoPlayTarget, clearAutoPlay } = useConversation(conversationId);
  const { contextPanelOpen, toggleContextPanel } = useConversationStore();
  useAutoPlay(autoPlayTarget, clearAutoPlay);
  const endRef = useRef<HTMLDivElement>(null);

  const messageCount = state.status === "ready" ? state.messages.length : 0;
  const hasStreaming = streamingMessage !== null;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messageCount, hasStreaming]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="border-b border-border px-4 py-2.5 flex-shrink-0 flex items-center gap-2 min-h-[42px]">
        <div className="flex-1 min-w-0">
          {state.status === "ready" ? (
            <p className="text-sm font-medium text-foreground truncate">
              {state.conversation.title}
            </p>
          ) : state.status === "loading" ? (
            <Skeleton className="h-4 w-48" />
          ) : null}
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleContextPanel}
          className={cn(
            "flex-shrink-0 h-7 w-7 text-muted-foreground hover:text-foreground",
            contextPanelOpen && "bg-secondary text-foreground"
          )}
          aria-label="Toggle documents panel"
        >
          <Files size={15} />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[720px] mx-auto px-4 py-6">
          {state.status === "loading" && <MessageSkeletons />}

          {state.status === "error" && (
            <div className="flex items-center justify-center py-16">
              <p className="text-sm text-muted-foreground">{state.message}</p>
            </div>
          )}

          {state.status === "ready" && (
            <div className="space-y-4">
              {state.messages.length === 0 && !streamingMessage ? (
                <p className="text-sm text-muted-foreground text-center py-16">
                  No messages yet.
                </p>
              ) : (
                state.messages.map((msg) => (
                  <MessageBubble key={msg.id} message={msg} />
                ))
              )}

              {streamingMessage && (
                <MessageBubble
                  message={{
                    id: "streaming",
                    role: "assistant",
                    content: streamingMessage.content || "…",
                    created_at: new Date().toISOString(),
                    citations: streamingMessage.citations.length > 0
                      ? streamingMessage.citations
                      : null,
                  }}
                  streaming
                />
              )}

              <div ref={endRef} />
            </div>
          )}
        </div>
      </div>

      <InputBar
        onSend={(content) => void send(content)}
        disabled={sending || state.status !== "ready"}
      />
    </div>
  );
}

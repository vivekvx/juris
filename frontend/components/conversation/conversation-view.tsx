"use client";
import { useEffect, useRef } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { InputBar } from "@/components/conversation/input-bar";
import { MessageBubble } from "@/components/conversation/message-bubble";
import { useConversation } from "@/hooks/use-conversation";

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
  const { state, sending, send } = useConversation(conversationId);
  const endRef = useRef<HTMLDivElement>(null);

  const messageCount = state.status === "ready" ? state.messages.length : 0;
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messageCount]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {state.status === "ready" && (
        <div className="border-b border-border px-4 py-2.5 flex-shrink-0">
          <p className="text-sm font-medium text-foreground truncate max-w-[600px]">
            {state.conversation.title}
          </p>
        </div>
      )}

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
              {state.messages.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-16">
                  No messages yet.
                </p>
              ) : (
                state.messages.map((msg) => (
                  <MessageBubble key={msg.id} message={msg} />
                ))
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

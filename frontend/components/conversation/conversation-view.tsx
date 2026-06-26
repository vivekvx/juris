"use client";
import { useEffect, useRef, useState } from "react";
import { Files, Scroll, ArrowDown } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { InputBar } from "@/components/conversation/input-bar";
import { MessageBubble } from "@/components/conversation/message-bubble";
import { EmptyConversation } from "@/components/conversation/empty-conversation";
import { useConversation } from "@/hooks/use-conversation";
import { useAutoPlay } from "@/hooks/use-auto-play";
import { useConversationStore } from "@/stores/conversation-store";

function MessageSkeletons() {
  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Skeleton className="h-10 w-48 rounded-2xl" />
      </div>
      <div className="space-y-1.5">
        <Skeleton className="h-4 w-full rounded" />
        <Skeleton className="h-4 w-5/6 rounded" />
        <Skeleton className="h-4 w-4/6 rounded" />
      </div>
      <div className="flex justify-end">
        <Skeleton className="h-10 w-36 rounded-2xl" />
      </div>
      <div className="space-y-1.5">
        <Skeleton className="h-4 w-full rounded" />
        <Skeleton className="h-4 w-3/4 rounded" />
      </div>
    </div>
  );
}

export function ConversationView({ conversationId }: { conversationId: string }) {
  const { state, sending, send, streamingMessage, autoPlayTarget, clearAutoPlay } = useConversation(conversationId);
  const {
    contextPanelOpen,
    toggleContextPanel,
    timelinePanelOpen,
    toggleTimelinePanel,
    setCurrentConversationId,
  } = useConversationStore();
  useAutoPlay(autoPlayTarget, clearAutoPlay);

  const endRef = useRef<HTMLDivElement>(null);
  const [atBottom, setAtBottom] = useState(true);

  useEffect(() => {
    setCurrentConversationId(conversationId);
    return () => { setCurrentConversationId(null); };
  }, [conversationId, setCurrentConversationId]);

  const messageCount = state.status === "ready" ? state.messages.length : 0;
  const hasStreaming = streamingMessage !== null;

  useEffect(() => {
    if (atBottom) {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messageCount, hasStreaming, atBottom]);

  useEffect(() => {
    const el = endRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => setAtBottom(entry?.isIntersecting ?? true),
      { threshold: 0.1 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  function scrollToBottom() {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }

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
          onClick={toggleTimelinePanel}
          className={cn(
            "hidden lg:flex flex-shrink-0 h-7 w-7 text-muted-foreground hover:text-foreground",
            timelinePanelOpen && "bg-secondary text-foreground",
          )}
          aria-label="Toggle decision log"
          aria-pressed={timelinePanelOpen}
        >
          <Scroll size={15} aria-hidden />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleContextPanel}
          className={cn(
            "flex-shrink-0 h-7 w-7 text-muted-foreground hover:text-foreground",
            contextPanelOpen && "bg-secondary text-foreground"
          )}
          aria-label="Toggle documents panel"
          aria-pressed={contextPanelOpen}
        >
          <Files size={15} aria-hidden />
        </Button>
      </div>

      <div className="relative flex-1 overflow-hidden">
        <div className="h-full overflow-y-auto">
          <div className="max-w-[720px] mx-auto px-4 py-8">
            {state.status === "loading" && <MessageSkeletons />}

            {state.status === "error" && (
              <div className="flex items-center justify-center py-16">
                <p className="text-sm text-muted-foreground">{state.message}</p>
              </div>
            )}

            {state.status === "ready" && (
              <div className="space-y-6">
                {state.messages.length === 0 && !streamingMessage ? (
                  <EmptyConversation />
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
                      content: streamingMessage.content,
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

        {!atBottom && (
          <button
            onClick={scrollToBottom}
            aria-label="Scroll to latest message"
            className="absolute bottom-4 right-4 flex items-center justify-center h-8 w-8 rounded-full bg-secondary border border-border text-muted-foreground hover:text-foreground hover:bg-secondary/80 shadow-sm transition-colors"
          >
            <ArrowDown size={14} aria-hidden />
          </button>
        )}
      </div>

      <InputBar
        onSend={(content) => void send(content)}
        disabled={sending || state.status !== "ready"}
      />
    </div>
  );
}

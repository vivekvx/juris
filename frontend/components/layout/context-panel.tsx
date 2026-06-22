"use client";
import { useConversationStore } from "@/stores/conversation-store";

export function ContextPanelDesktop() {
  const { contextPanelOpen } = useConversationStore();
  if (!contextPanelOpen) return null;
  return (
    <aside className="w-80 flex-shrink-0 border-l border-border bg-card flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <p className="text-label text-muted-foreground">Context</p>
      </div>
      <div className="flex-1 overflow-y-auto">
        {/* Sources, Timeline, Files, Memories — reserved for M3+ */}
      </div>
    </aside>
  );
}

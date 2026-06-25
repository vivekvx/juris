"use client";
import { useConversationStore } from "@/stores/conversation-store";
import { DecisionTimelineList } from "@/components/conversation/decision-timeline-list";

export function DecisionTimelinePanelDesktop() {
  const { timelinePanelOpen, currentConversationId } = useConversationStore();

  if (!timelinePanelOpen || !currentConversationId) return null;

  return (
    <aside
      className="w-72 flex-shrink-0 border-l border-border bg-card flex flex-col overflow-hidden"
      aria-label="Decision timeline"
    >
      <div className="px-4 py-3 border-b border-border flex-shrink-0">
        <p className="text-[0.6875rem] font-medium text-muted-foreground/60 uppercase tracking-widest">
          Decision Log
        </p>
      </div>
      <DecisionTimelineList conversationId={currentConversationId} />
    </aside>
  );
}

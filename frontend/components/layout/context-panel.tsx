"use client";
import { useConversationStore } from "@/stores/conversation-store";
import { ContextPanelDocuments } from "@/components/layout/context-panel-documents";

export function ContextPanelDesktop() {
  const { contextPanelOpen } = useConversationStore();
  if (!contextPanelOpen) return null;
  return (
    <aside className="w-72 flex-shrink-0 border-l border-border bg-card flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex-shrink-0">
        <p className="text-[0.6875rem] font-medium text-muted-foreground/60 uppercase tracking-widest">
          Documents
        </p>
      </div>
      <div className="flex-1 overflow-y-auto">
        <ContextPanelDocuments />
      </div>
    </aside>
  );
}

"use client";
import { useConversationStore } from "@/stores/conversation-store";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { ContextPanelDocuments } from "@/components/layout/context-panel-documents";

export function ContextPanelMobile() {
  const { contextPanelOpen, toggleContextPanel } = useConversationStore();
  return (
    <Drawer open={contextPanelOpen} onOpenChange={(o) => !o && toggleContextPanel()}>
      <DrawerContent>
        <div className="px-4 py-3 border-b border-border flex-shrink-0">
          <p className="text-[0.6875rem] font-medium text-muted-foreground/60 uppercase tracking-widest">
            Documents
          </p>
        </div>
        <div className="flex-1 overflow-y-auto pb-8">
          <ContextPanelDocuments />
        </div>
      </DrawerContent>
    </Drawer>
  );
}

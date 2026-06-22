"use client";
import { useConversationStore } from "@/stores/conversation-store";
import { Drawer, DrawerContent } from "@/components/ui/drawer";

export function ContextPanelMobile() {
  const { contextPanelOpen, toggleContextPanel } = useConversationStore();
  return (
    <Drawer open={contextPanelOpen} onOpenChange={(o) => !o && toggleContextPanel()}>
      <DrawerContent>
        <div className="px-4 py-3 border-b border-border">
          <p className="text-label text-muted-foreground">Context</p>
        </div>
        <div className="flex-1 overflow-y-auto p-4 pb-8">
          {/* Sources, Timeline, Files, Memories — reserved for M3+ */}
        </div>
      </DrawerContent>
    </Drawer>
  );
}

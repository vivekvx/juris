"use client";
import { Sidebar } from "@/components/layout/sidebar";
import { ConversationPanel } from "@/components/layout/conversation-panel";
import { ContextPanel } from "@/components/layout/context-panel";
import { useUIStore } from "@/stores/ui";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children?: React.ReactNode }) {
  const { sidebarCollapsed, contextPanelOpen } = useUIStore();

  return (
    <div className="flex h-full w-full overflow-hidden bg-background">
      <Sidebar collapsed={sidebarCollapsed} />
      <main className="flex flex-1 overflow-hidden">
        <ConversationPanel>{children}</ConversationPanel>
        <ContextPanel open={contextPanelOpen} />
      </main>
    </div>
  );
}

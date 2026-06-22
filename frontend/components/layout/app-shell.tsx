import { SidebarDesktop } from "@/components/layout/sidebar";
import { SidebarMobile } from "@/components/layout/sidebar-mobile";
import { ConversationPanel } from "@/components/layout/conversation-panel";
import { ContextPanelDesktop } from "@/components/layout/context-panel";
import { ContextPanelMobile } from "@/components/layout/context-panel-mobile";

export function AppShell({ children }: { children?: React.ReactNode }) {
  return (
    <div className="flex h-full w-full overflow-hidden bg-background">
      <div className="hidden md:flex">
        <SidebarDesktop />
      </div>
      <SidebarMobile />
      <main className="flex flex-1 overflow-hidden min-w-0">
        <ConversationPanel>{children}</ConversationPanel>
        <div className="hidden lg:flex">
          <ContextPanelDesktop />
        </div>
        <ContextPanelMobile />
      </main>
    </div>
  );
}

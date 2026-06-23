import { AppShell } from "@/components/layout/app-shell";
import { EmptyConversation } from "@/components/conversation/empty-conversation";
import { InputBar } from "@/components/conversation/input-bar";

export default function WorkspacePage() {
  return (
    <AppShell>
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          <EmptyConversation />
        </div>
        <InputBar />
      </div>
    </AppShell>
  );
}

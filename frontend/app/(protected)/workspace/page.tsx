import { AppShell } from "@/components/layout/app-shell";
import { WorkspaceView } from "@/components/conversation/workspace-view";

export default function WorkspacePage() {
  return (
    <AppShell>
      <WorkspaceView />
    </AppShell>
  );
}

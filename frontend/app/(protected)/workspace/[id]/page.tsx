import { AppShell } from "@/components/layout/app-shell";
import { ConversationView } from "@/components/conversation/conversation-view";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <AppShell>
      <ConversationView conversationId={id} />
    </AppShell>
  );
}

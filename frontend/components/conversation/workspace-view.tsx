"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { getAuth } from "@/lib/firebase";
import { createConversation } from "@/lib/api";
import { EmptyConversation } from "@/components/conversation/empty-conversation";
import { InputBar } from "@/components/conversation/input-bar";

function titleFromContent(content: string): string {
  const clean = content.trim().replace(/\s+/g, " ");
  return clean.length <= 60 ? clean : `${clean.slice(0, 57)}…`;
}

export function WorkspaceView() {
  const router = useRouter();
  const [sending, setSending] = useState(false);

  function handleSend(content: string) {
    setSending(true);
    void (async () => {
      try {
        const currentUser = getAuth().currentUser;
        if (!currentUser) {
          toast.error("Session expired. Please sign in again.");
          return;
        }
        const idToken = await currentUser.getIdToken();
        const conv = await createConversation(titleFromContent(content), idToken);
        // Pass initial message to ConversationView via sessionStorage
        sessionStorage.setItem("juris_initial_msg", content);
        router.push(`/workspace/${conv.id}`);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to start conversation.");
        setSending(false);
      }
    })();
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <EmptyConversation />
      </div>
      <InputBar onSend={handleSend} disabled={sending} />
    </div>
  );
}

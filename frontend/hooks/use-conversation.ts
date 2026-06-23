"use client";
import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { getAuth } from "@/lib/firebase";
import { listConversations, listMessages, sendMessage } from "@/lib/api";
import type { ConversationResponse, MessageResponse } from "@/types/conversation";

type State =
  | { status: "loading" }
  | { status: "ready"; conversation: ConversationResponse; messages: MessageResponse[] }
  | { status: "error"; message: string };

export function useConversation(id: string) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [sending, setSending] = useState(false);

  const load = useCallback(async () => {
    setState({ status: "loading" });
    try {
      const currentUser = getAuth().currentUser;
      if (!currentUser) throw new Error("Not authenticated.");
      const idToken = await currentUser.getIdToken();

      const [conversations, messages] = await Promise.all([
        listConversations(idToken),
        listMessages(id, idToken),
      ]);
      const conversation = conversations.find((c) => c.id === id);
      if (!conversation) throw new Error("Conversation not found.");

      setState({ status: "ready", conversation, messages });
    } catch (err) {
      setState({
        status: "error",
        message: err instanceof Error ? err.message : "Failed to load conversation.",
      });
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  const send = useCallback(
    async (content: string) => {
      if (state.status !== "ready") return;
      setSending(true);
      try {
        const currentUser = getAuth().currentUser;
        if (!currentUser) throw new Error("Session expired.");
        const idToken = await currentUser.getIdToken();
        const msg = await sendMessage(id, content, idToken);
        setState((prev) =>
          prev.status === "ready"
            ? { ...prev, messages: [...prev.messages, msg] }
            : prev,
        );
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to send message.");
      } finally {
        setSending(false);
      }
    },
    [id, state.status],
  );

  return { state, sending, send, refetch: load };
}

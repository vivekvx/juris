"use client";
import { useState, useCallback } from "react";
import { getAuth } from "@/lib/firebase";
import { listConversations } from "@/lib/api";
import type { ConversationResponse } from "@/types/conversation";

export type ConversationsState =
  | { status: "loading" }
  | { status: "ready"; conversations: ConversationResponse[] }
  | { status: "error" };

export function useConversations() {
  const [state, setState] = useState<ConversationsState>({ status: "loading" });

  const load = useCallback(async () => {
    setState({ status: "loading" });
    try {
      const currentUser = getAuth().currentUser;
      if (!currentUser) {
        setState({ status: "ready", conversations: [] });
        return;
      }
      const idToken = await currentUser.getIdToken();
      const conversations = await listConversations(idToken);
      setState({ status: "ready", conversations });
    } catch {
      setState({ status: "error" });
    }
  }, []);

  return { state, load };
}

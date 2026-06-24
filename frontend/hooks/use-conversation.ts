"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { toast } from "sonner";
import { getAuth } from "@/lib/firebase";
import { listConversations, listMessages } from "@/lib/api";
import type { Citation, ConversationResponse, MessageResponse } from "@/types/conversation";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8001";

type State =
  | { status: "loading" }
  | { status: "ready"; conversation: ConversationResponse; messages: MessageResponse[] }
  | { status: "error"; message: string };

export type StreamingMessage = {
  content: string;
  citations: Citation[];
  sources_used: boolean;
};

async function* parseSSE(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): AsyncGenerator<{ event: string; data: string }> {
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      if (!block.trim()) continue;
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7).trim();
        else if (line.startsWith("data: ")) data = line.slice(6);
      }
      if (data) yield { event, data };
    }
  }
}

export function useConversation(id: string) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [sending, setSending] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState<StreamingMessage | null>(null);
  const initialMsgRef = useRef<string | null>(null);

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

  // Check for message passed via sessionStorage (from workspace new-chat flow)
  useEffect(() => {
    const initial = sessionStorage.getItem("juris_initial_msg");
    if (initial) {
      sessionStorage.removeItem("juris_initial_msg");
      initialMsgRef.current = initial;
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const send = useCallback(
    async (content: string) => {
      if (state.status !== "ready") return;
      setSending(true);

      // Optimistically add user message
      const optimisticUserMsg: MessageResponse = {
        id: `optimistic-${Date.now()}`,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };
      setState((prev) =>
        prev.status === "ready"
          ? { ...prev, messages: [...prev.messages, optimisticUserMsg] }
          : prev,
      );
      setStreamingMessage({ content: "", citations: [], sources_used: false });

      try {
        const currentUser = getAuth().currentUser;
        if (!currentUser) throw new Error("Session expired.");
        const idToken = await currentUser.getIdToken();

        const response = await fetch(`${BACKEND_URL}/api/conversations/${id}/messages`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${idToken}`,
          },
          body: JSON.stringify({ content }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`Request failed: ${response.status}`);
        }

        const reader = response.body.getReader();
        let accumulated = "";
        let citations: Citation[] = [];
        let sourcesUsed = false;

        for await (const { event, data } of parseSSE(reader)) {
          const parsed = JSON.parse(data) as Record<string, unknown>;

          if (event === "token") {
            accumulated += parsed.text as string;
            setStreamingMessage({ content: accumulated, citations, sources_used: sourcesUsed });
          } else if (event === "citations") {
            citations = (parsed.citations as Citation[]) ?? [];
            sourcesUsed = Boolean(parsed.sources_used);
            setStreamingMessage({ content: accumulated, citations, sources_used: sourcesUsed });
          } else if (event === "done") {
            const finalMsg: MessageResponse = {
              id: parsed.message_id as string,
              role: "assistant",
              content: accumulated,
              created_at: new Date().toISOString(),
              citations: citations.length > 0 ? citations : null,
            };
            setState((prev) =>
              prev.status === "ready"
                ? { ...prev, messages: [...prev.messages, finalMsg] }
                : prev,
            );
            setStreamingMessage(null);
          } else if (event === "error") {
            throw new Error((parsed.detail as string) ?? "Stream error");
          }
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to send message.");
        // Remove optimistic user message on failure
        setState((prev) =>
          prev.status === "ready"
            ? { ...prev, messages: prev.messages.filter((m) => m.id !== optimisticUserMsg.id) }
            : prev,
        );
        setStreamingMessage(null);
      } finally {
        setSending(false);
      }
    },
    [id, state.status],
  );

  // Auto-send initial message once conversation is ready
  useEffect(() => {
    if (state.status === "ready" && initialMsgRef.current) {
      const msg = initialMsgRef.current;
      initialMsgRef.current = null;
      void send(msg);
    }
  }, [state.status, send]);

  return { state, sending, send, streamingMessage, refetch: load };
}

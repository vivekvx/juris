"use client";
import { useState, useEffect, useCallback } from "react";
import { getAuth } from "@/lib/firebase";
import { fetchDecisionTimeline } from "@/lib/api";
import type { LedgerEntryResponse } from "@/types/ledger";

type TimelineState =
  | { status: "loading" }
  | { status: "ready"; entries: LedgerEntryResponse[]; total: number }
  | { status: "error"; message: string };

export type { TimelineState };

export function useDecisionTimeline(conversationId: string | null) {
  const [state, setState] = useState<TimelineState>({ status: "loading" });

  const load = useCallback(async () => {
    if (!conversationId) {
      setState({ status: "ready", entries: [], total: 0 });
      return;
    }
    setState({ status: "loading" });
    try {
      const currentUser = getAuth().currentUser;
      if (!currentUser) throw new Error("Not authenticated.");
      const idToken = await currentUser.getIdToken();
      const data = await fetchDecisionTimeline(conversationId, idToken);
      setState({ status: "ready", entries: data.entries, total: data.total });
    } catch (err) {
      setState({
        status: "error",
        message:
          err instanceof Error ? err.message : "Failed to load decision timeline.",
      });
    }
  }, [conversationId]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load]);

  return { state, refetch: load };
}

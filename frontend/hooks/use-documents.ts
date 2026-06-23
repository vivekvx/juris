"use client";
import { useState, useEffect, useCallback } from "react";
import { getAuth } from "@/lib/firebase";
import { listDocuments } from "@/lib/api";
import type { DocumentResponse } from "@/types/document";

export type DocumentsState =
  | { status: "loading" }
  | { status: "ready"; documents: DocumentResponse[] }
  | { status: "error"; message: string };

export function useDocuments() {
  const [state, setState] = useState<DocumentsState>({ status: "loading" });

  const load = useCallback(async () => {
    setState({ status: "loading" });
    try {
      const currentUser = getAuth().currentUser;
      if (!currentUser) {
        setState({ status: "error", message: "Session expired. Please sign in again." });
        return;
      }
      const idToken = await currentUser.getIdToken();
      const documents = await listDocuments(idToken);
      setState({ status: "ready", documents });
    } catch (err) {
      setState({
        status: "error",
        message: err instanceof Error ? err.message : "Failed to load documents.",
      });
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return { state, refetch: load };
}

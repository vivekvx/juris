"use client";
import { create } from "zustand";

interface ConversationStore {
  contextPanelOpen: boolean;
  toggleContextPanel: () => void;
}

export const useConversationStore = create<ConversationStore>((set) => ({
  contextPanelOpen: true,
  toggleContextPanel: () => set((s) => ({ contextPanelOpen: !s.contextPanelOpen })),
}));

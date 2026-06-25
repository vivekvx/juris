"use client";
import { create } from "zustand";

interface ConversationStore {
  contextPanelOpen: boolean;
  toggleContextPanel: () => void;
  timelinePanelOpen: boolean;
  toggleTimelinePanel: () => void;
  currentConversationId: string | null;
  setCurrentConversationId: (id: string | null) => void;
}

export const useConversationStore = create<ConversationStore>((set) => ({
  contextPanelOpen: false,
  // Opening context panel closes timeline panel (one right panel at a time).
  toggleContextPanel: () =>
    set((s) => ({
      contextPanelOpen: !s.contextPanelOpen,
      timelinePanelOpen: !s.contextPanelOpen ? false : s.timelinePanelOpen,
    })),

  timelinePanelOpen: false,
  // Opening timeline panel closes context panel (one right panel at a time).
  toggleTimelinePanel: () =>
    set((s) => ({
      timelinePanelOpen: !s.timelinePanelOpen,
      contextPanelOpen: !s.timelinePanelOpen ? false : s.contextPanelOpen,
    })),

  currentConversationId: null,
  setCurrentConversationId: (id) => set({ currentConversationId: id }),
}));

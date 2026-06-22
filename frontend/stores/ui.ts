"use client";
import { create } from "zustand";

interface UIStore {
  sidebarCollapsed: boolean;
  contextPanelOpen: boolean;
  toggleSidebar: () => void;
  toggleContextPanel: () => void;
}

export const useUIStore = create<UIStore>((set) => ({
  sidebarCollapsed: false,
  contextPanelOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  toggleContextPanel: () => set((s) => ({ contextPanelOpen: !s.contextPanelOpen })),
}));

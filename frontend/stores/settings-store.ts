"use client";
import { create } from "zustand";
import type { Language } from "@/types";

interface SettingsStore {
  language: Language;
  setLanguage: (lang: Language) => void;
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  language: "en",
  setLanguage: (language) => set({ language }),
}));

import { ChatCircle, Files, Microphone, Brain, type Icon } from "@phosphor-icons/react";

export interface NavItem {
  href: string;
  icon: Icon;
  label: string;
}

export const NAV: NavItem[] = [
  { href: "/workspace", icon: ChatCircle, label: "Workspace" },
  { href: "/documents", icon: Files, label: "Documents" },
  { href: "/voice", icon: Microphone, label: "Voice" },
  { href: "/memory", icon: Brain, label: "Memory" },
];

"use client";
import { cn } from "@/lib/utils";

interface ContextPanelProps {
  open: boolean;
}

export function ContextPanel({ open }: ContextPanelProps) {
  if (!open) return null;
  return (
    <aside className="w-80 flex-shrink-0 border-l border-border bg-card flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <p className="text-label text-muted-foreground">Context</p>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <p className="text-caption text-muted-foreground">Citations and sources appear here.</p>
      </div>
    </aside>
  );
}

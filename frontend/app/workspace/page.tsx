import { AppShell } from "@/components/layout/app-shell";

export default function WorkspacePage() {
  return (
    <AppShell>
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="text-center">
          <p className="text-display text-foreground mb-2">Good evening</p>
          <p className="text-body-lg text-muted-foreground">Ask a legal question in any language</p>
        </div>
      </div>
    </AppShell>
  );
}

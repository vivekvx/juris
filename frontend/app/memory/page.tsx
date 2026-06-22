import { AppShell } from "@/components/layout/app-shell";

export default function MemoryPage() {
  return (
    <AppShell>
      <div className="p-8">
        <h1 className="text-heading mb-4">Memory</h1>
        <p className="text-body-lg text-muted-foreground">Your saved cases and context.</p>
      </div>
    </AppShell>
  );
}

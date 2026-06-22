import { AppShell } from "@/components/layout/app-shell";

export default function VoicePage() {
  return (
    <AppShell>
      <div className="p-8">
        <h1 className="text-heading mb-4">Voice</h1>
        <p className="text-body-lg text-muted-foreground">Speak your legal queries in your language.</p>
      </div>
    </AppShell>
  );
}

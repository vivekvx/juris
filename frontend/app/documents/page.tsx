import { AppShell } from "@/components/layout/app-shell";

export default function DocumentsPage() {
  return (
    <AppShell>
      <div className="p-8">
        <h1 className="text-heading mb-4">Documents</h1>
        <p className="text-body-lg text-muted-foreground">Upload and manage legal documents.</p>
      </div>
    </AppShell>
  );
}

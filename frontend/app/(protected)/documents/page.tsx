import { AppShell } from "@/components/layout/app-shell";
import { UploadZone } from "@/components/documents/upload-zone";

export default function DocumentsPage() {
  return (
    <AppShell>
      <div className="p-8 max-w-xl space-y-6">
        <div>
          <h1 className="text-heading mb-1">Documents</h1>
          <p className="text-[0.875rem] text-muted-foreground">Upload legal documents for analysis.</p>
        </div>
        <UploadZone />
      </div>
    </AppShell>
  );
}

"use client";
import { Files } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocuments } from "@/hooks/use-documents";

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function mimeLabel(mime: string): string {
  if (mime === "application/pdf") return "PDF";
  if (mime.includes("wordprocessingml")) return "DOCX";
  if (mime === "text/plain") return "TXT";
  return "FILE";
}

export function ContextPanelDocuments() {
  const { state } = useDocuments();

  if (state.status === "loading") {
    return (
      <div className="space-y-2 p-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-10 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  const readyDocs =
    state.status === "ready"
      ? state.documents.filter((d) => d.status === "READY")
      : [];

  if (readyDocs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 px-4 py-8 text-center">
        <Files size={22} className="text-muted-foreground/30" weight="thin" />
        <p className="text-[0.75rem] text-muted-foreground leading-relaxed">
          No documents yet.
          <br />
          Upload from the Documents section.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-px p-2">
      {readyDocs.map((doc) => (
        <div
          key={doc.id}
          className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 hover:bg-secondary transition-colors"
        >
          <Badge variant="outline" className="shrink-0 font-mono text-[0.6rem] uppercase">
            {mimeLabel(doc.mime_type)}
          </Badge>
          <div className="flex-1 min-w-0">
            <p
              className="text-[0.8125rem] text-foreground truncate"
              title={doc.original_filename}
            >
              {doc.original_filename}
            </p>
            <p className="text-[0.7rem] text-muted-foreground">
              {formatSize(doc.size_bytes)}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

"use client";
import { useState } from "react";
import { Trash } from "@phosphor-icons/react";
import { toast } from "sonner";
import { getAuth } from "@/lib/firebase";
import { deleteDocument } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { DocumentResponse, DocumentStatus } from "@/types/document";
import type { DocumentsState } from "@/hooks/use-documents";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(iso));
}

function mimeLabel(mime: string): string {
  if (mime === "application/pdf") return "PDF";
  if (mime.includes("wordprocessingml")) return "DOCX";
  if (mime === "text/plain") return "TXT";
  return "FILE";
}

const STATUS_VARIANT: Record<DocumentStatus, "outline" | "destructive" | "secondary"> = {
  READY: "outline",
  FAILED: "destructive",
  UPLOADING: "secondary",
  PROCESSING: "secondary",
};

function DocumentRow({
  doc,
  onDeleted,
}: {
  doc: DocumentResponse;
  onDeleted: () => void;
}) {
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      const currentUser = getAuth().currentUser;
      if (!currentUser) {
        toast.error("Session expired. Please sign in again.");
        return;
      }
      const idToken = await currentUser.getIdToken();
      await deleteDocument(doc.id, idToken);
      onDeleted();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete document.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
      <Badge variant="outline" className="shrink-0 font-mono text-[0.65rem] uppercase">
        {mimeLabel(doc.mime_type)}
      </Badge>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground truncate" title={doc.original_filename}>
          {doc.original_filename}
        </p>
        <p className="text-[0.75rem] text-muted-foreground">
          {formatSize(doc.size_bytes)} · {formatDate(doc.created_at)}
        </p>
        {doc.status === "FAILED" && doc.error_message && (
          <p className="text-[0.75rem] text-destructive mt-0.5">{doc.error_message}</p>
        )}
      </div>

      <Badge variant={STATUS_VARIANT[doc.status]} className="shrink-0 capitalize">
        {doc.status.toLowerCase()}
      </Badge>

      <Button
        variant="ghost"
        size="icon-sm"
        onClick={() => void handleDelete()}
        disabled={deleting}
        aria-label={`Delete ${doc.original_filename}`}
        className="shrink-0 text-muted-foreground hover:text-destructive"
      >
        <Trash size={14} />
      </Button>
    </div>
  );
}

export function DocumentList({
  state,
  refetch,
}: {
  state: DocumentsState;
  refetch: () => void;
}) {
  if (state.status === "loading") {
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-[3.75rem] w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="rounded-xl border border-border bg-card px-4 py-4">
        <p className="text-sm text-destructive">{state.message}</p>
        <button
          type="button"
          onClick={refetch}
          className="mt-2 text-[0.75rem] text-primary underline-offset-4 hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  if (state.documents.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No documents yet. Upload your first document above.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {state.documents.map((doc) => (
        <DocumentRow key={doc.id} doc={doc} onDeleted={refetch} />
      ))}
    </div>
  );
}

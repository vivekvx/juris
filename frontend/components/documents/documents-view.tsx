"use client";
import { UploadZone } from "@/components/documents/upload-zone";
import { DocumentList } from "@/components/documents/document-list";
import { useDocuments } from "@/hooks/use-documents";

export function DocumentsView() {
  const { state, refetch } = useDocuments();

  return (
    <div className="space-y-6">
      <UploadZone onSuccess={refetch} />
      <DocumentList state={state} refetch={refetch} />
    </div>
  );
}

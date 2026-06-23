"use client";

import { useRef, useState } from "react";
import { getAuth } from "@/lib/firebase";
import { uploadDocument } from "@/lib/api";
import type { DocumentResponse } from "@/types/document";

const ALLOWED_TYPES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
]);

const MAX_BYTES = 20 * 1024 * 1024;

type UploadState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "success"; document: DocumentResponse }
  | { status: "error"; message: string };

function validate(file: File): string | null {
  if (!ALLOWED_TYPES.has(file.type)) {
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "unknown";
    return `.${ext} files are not supported. Please upload a PDF, DOCX, or TXT file.`;
  }
  if (file.size > MAX_BYTES) {
    const mb = (file.size / 1024 / 1024).toFixed(1);
    return `File is ${mb} MB. Maximum allowed size is 20 MB.`;
  }
  return null;
}

export function UploadZone() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<UploadState>({ status: "idle" });

  async function handleFile(file: File) {
    const error = validate(file);
    if (error) {
      setState({ status: "error", message: error });
      return;
    }

    setState({ status: "uploading" });

    try {
      const currentUser = getAuth().currentUser;
      if (!currentUser) {
        setState({ status: "error", message: "Session expired. Please sign in again." });
        return;
      }
      const idToken = await currentUser.getIdToken();
      const doc = await uploadDocument(file, idToken);
      setState({ status: "success", document: doc });
    } catch (err) {
      const message =
        err instanceof Error && err.message !== "Failed to fetch"
          ? err.message
          : "Could not reach the server. Check your connection and try again.";
      setState({ status: "error", message });
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void handleFile(file);
    e.target.value = "";
  }

  const uploading = state.status === "uploading";

  return (
    <div className="rounded-xl border border-border bg-card p-6 space-y-4">
      <div className="space-y-0.5">
        <h2 className="text-sm font-medium text-foreground">Upload Document</h2>
        <p className="text-[0.75rem] text-muted-foreground">PDF, DOCX, or TXT · Max 20 MB</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
        onChange={handleChange}
        disabled={uploading}
        className="sr-only"
        aria-label="Upload document"
      />

      {state.status === "success" ? (
        <div className="space-y-3">
          <div
            role="status"
            className="rounded-xl border border-border bg-background px-4 py-4 space-y-0.5"
          >
            <p className="text-sm font-medium text-foreground">
              {state.document.original_filename}
            </p>
            <p className="text-[0.75rem] text-muted-foreground">Upload complete</p>
          </div>
          <button
            type="button"
            onClick={() => setState({ status: "idle" })}
            className="text-[0.75rem] text-primary underline-offset-4 hover:underline"
          >
            Upload another file
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="w-full rounded-xl border border-dashed border-border bg-background px-4 py-8 text-sm text-muted-foreground hover:border-primary hover:text-foreground transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {uploading ? "Uploading…" : "Click to choose a file"}
        </button>
      )}

      {state.status === "error" && (
        <p role="alert" className="text-[0.75rem] text-destructive">
          {state.message}
        </p>
      )}
    </div>
  );
}

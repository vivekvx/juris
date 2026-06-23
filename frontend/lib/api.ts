import type { DocumentResponse } from "@/types/document";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8001";

export async function listDocuments(idToken: string): Promise<DocumentResponse[]> {
  const res = await fetch(`${BACKEND_URL}/api/documents/`, {
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!res.ok) throw new Error("Failed to load documents.");
  return res.json() as Promise<DocumentResponse[]>;
}

export async function deleteDocument(id: string, idToken: string): Promise<void> {
  const res = await fetch(`${BACKEND_URL}/api/documents/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!res.ok) throw new Error("Failed to delete document.");
}

export async function backendPost(
  path: string,
  idToken: string,
  body?: unknown,
): Promise<Response> {
  return fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export async function uploadDocument(
  file: File,
  idToken: string,
): Promise<DocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BACKEND_URL}/api/documents/`, {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}` },
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { detail?: unknown };
    const detail =
      typeof body.detail === "string" ? body.detail : "Upload failed. Please try again.";
    throw new Error(detail);
  }

  return res.json() as Promise<DocumentResponse>;
}

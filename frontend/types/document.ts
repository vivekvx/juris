export type DocumentStatus = "UPLOADING" | "PROCESSING" | "READY" | "FAILED";

export type DocumentResponse = {
  id: string;
  filename: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

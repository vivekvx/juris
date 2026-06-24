export type Citation = {
  doc_id: string;
  original_filename: string;
  chunk_index: number;
  page_number: number | null;
  content: string;
  score: number;
};

export type ConversationResponse = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  document_ids: string[] | null;
};

export type MessageResponse = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  citations?: Citation[] | null;
};

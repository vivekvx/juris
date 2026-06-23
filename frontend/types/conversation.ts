export type ConversationResponse = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
};

export type MessageResponse = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

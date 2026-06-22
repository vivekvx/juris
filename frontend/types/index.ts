export type Language = "en" | "hi" | "kn" | "ta" | "te";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  language: Language;
  createdAt: Date;
}

export interface Conversation {
  id: string;
  title: string;
  language: Language;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

export interface Document {
  id: string;
  name: string;
  type: string;
  size: number;
  uploadedAt: Date;
  conversationId?: string;
}

export interface Citation {
  id: string;
  text: string;
  source: string;
  page?: number;
  relevance: number;
}

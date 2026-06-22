import type { Message } from "@/types";
import { MessageGroup } from "./message-group";

interface MessageListProps {
  messages: Message[];
}

export function MessageList({ messages }: MessageListProps) {
  if (!messages.length) return null;
  return (
    <div className="flex flex-col py-4">
      {messages.map((msg) => (
        <MessageGroup key={msg.id} message={msg} />
      ))}
    </div>
  );
}

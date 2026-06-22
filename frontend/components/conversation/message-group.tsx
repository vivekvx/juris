import type { Message } from "@/types";
import { MessageBubble } from "./message-bubble";

interface MessageGroupProps {
  message: Message;
}

export function MessageGroup({ message }: MessageGroupProps) {
  return (
    <div className="px-4 py-1">
      <MessageBubble message={message} />
    </div>
  );
}

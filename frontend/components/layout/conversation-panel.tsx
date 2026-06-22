import { cn } from "@/lib/utils";

interface ConversationPanelProps {
  children?: React.ReactNode;
  className?: string;
}

export function ConversationPanel({ children, className }: ConversationPanelProps) {
  return (
    <div className={cn("flex flex-1 flex-col overflow-hidden", className)}>
      <div className="flex flex-1 justify-center overflow-y-auto">
        <div className="w-full max-w-[720px] flex flex-col min-h-full">
          {children}
        </div>
      </div>
    </div>
  );
}

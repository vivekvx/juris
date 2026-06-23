"use client";
import { useState, useRef } from "react";
import { PaperPlaneRight } from "@phosphor-icons/react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

export function InputBar() {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  function handleSubmit() {
    if (!value.trim()) return;
    setValue("");
    ref.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="border-t border-border bg-background px-4 py-3">
      <div className="flex gap-2 items-end max-w-[720px] mx-auto">
        <Textarea
          ref={ref}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a legal question… (Shift+Enter for new line)"
          className="resize-none min-h-[44px] max-h-[200px]"
          rows={1}
        />
        <Button
          size="icon"
          onClick={handleSubmit}
          disabled={!value.trim()}
          className="flex-shrink-0 h-11 w-11"
          aria-label="Send"
        >
          <PaperPlaneRight size={18} />
        </Button>
      </div>
    </div>
  );
}

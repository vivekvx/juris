import { render, screen, fireEvent } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import React from "react";
import { InputBar } from "../input-bar";

// Stub MicButton so we can trigger onTranscript directly without real mic/network
vi.mock("../mic-button", () => ({
  MicButton: ({
    onTranscript,
    disabled,
  }: {
    onTranscript: (text: string) => void;
    disabled?: boolean;
  }) => (
    <button
      onClick={() => onTranscript("voice transcript text")}
      disabled={disabled}
      aria-label="mock-mic"
    >
      mic
    </button>
  ),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("InputBar — voice integration", () => {
  it("transcript populates textarea and can be sent unchanged", () => {
    const onSend = vi.fn();
    render(<InputBar onSend={onSend} />);

    // Trigger transcript via MicButton stub
    fireEvent.click(screen.getByRole("button", { name: "mock-mic" }));

    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveValue("voice transcript text");

    // Send via button click — calls existing onSend with transcript text
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(onSend).toHaveBeenCalledOnce();
    expect(onSend).toHaveBeenCalledWith("voice transcript text");
  });

  it("transcript is editable before sending", () => {
    const onSend = vi.fn();
    render(<InputBar onSend={onSend} />);

    fireEvent.click(screen.getByRole("button", { name: "mock-mic" }));
    const textarea = screen.getByRole("textbox");

    // User edits the transcript
    fireEvent.change(textarea, { target: { value: "edited transcript" } });
    expect(textarea).toHaveValue("edited transcript");

    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(onSend).toHaveBeenCalledWith("edited transcript");
  });

  it("send button stays disabled until textarea has content", () => {
    render(<InputBar onSend={vi.fn()} />);
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "mock-mic" }));
    expect(screen.getByRole("button", { name: /send/i })).not.toBeDisabled();
  });

  it("textarea clears after send", () => {
    const onSend = vi.fn();
    render(<InputBar onSend={onSend} />);

    fireEvent.click(screen.getByRole("button", { name: "mock-mic" }));
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(screen.getByRole("textbox")).toHaveValue("");
  });

  it("Enter key sends transcript same as button click", () => {
    const onSend = vi.fn();
    render(<InputBar onSend={onSend} />);

    fireEvent.click(screen.getByRole("button", { name: "mock-mic" }));
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });

    expect(onSend).toHaveBeenCalledWith("voice transcript text");
  });

  it("disabled prop disables mic button", () => {
    render(<InputBar onSend={vi.fn()} disabled />);
    expect(screen.getByRole("button", { name: "mock-mic" })).toBeDisabled();
  });

  it("typed text and voice transcript use the same send path", () => {
    const onSend = vi.fn();
    render(<InputBar onSend={onSend} />);

    // Type manually
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "typed text" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(onSend).toHaveBeenNthCalledWith(1, "typed text");

    // Voice transcript
    fireEvent.click(screen.getByRole("button", { name: "mock-mic" }));
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(onSend).toHaveBeenNthCalledWith(2, "voice transcript text");
  });
});

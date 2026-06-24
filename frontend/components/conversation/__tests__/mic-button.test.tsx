import { render, screen, fireEvent } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import React from "react";
import { MicButton } from "../mic-button";
import type { UseRecorderReturn, RecorderState } from "@/hooks/use-recorder";

// ── Mock useRecorder ───────────────────────────────────────────────────────

vi.mock("@/hooks/use-recorder", () => ({
  useRecorder: vi.fn(),
}));

import { useRecorder } from "@/hooks/use-recorder";

function makeRecorder(
  phase: RecorderState,
  overrides?: Partial<UseRecorderReturn>,
): UseRecorderReturn {
  return {
    recorderState: phase,
    start: vi.fn(),
    stop: vi.fn(),
    cancel: vi.fn(),
    retry: vi.fn(),
    ...overrides,
  };
}

const mockUseRecorder = vi.mocked(useRecorder);

beforeEach(() => {
  vi.clearAllMocks();
});

// ── Tests ──────────────────────────────────────────────────────────────────

describe("MicButton", () => {
  it("renders mic button in idle state", () => {
    mockUseRecorder.mockReturnValue(makeRecorder({ phase: "idle" }));
    render(<MicButton onTranscript={vi.fn()} />);
    expect(screen.getByRole("button", { name: /start voice recording/i })).toBeInTheDocument();
  });

  it("calls start() when idle button clicked", () => {
    const start = vi.fn();
    mockUseRecorder.mockReturnValue(makeRecorder({ phase: "idle" }, { start }));
    render(<MicButton onTranscript={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /start voice recording/i }));
    expect(start).toHaveBeenCalledTimes(1);
  });

  it("shows requesting state as disabled mic button", () => {
    mockUseRecorder.mockReturnValue(makeRecorder({ phase: "requesting" }));
    render(<MicButton onTranscript={vi.fn()} />);
    const btn = screen.getByRole("button", { name: /requesting microphone/i });
    expect(btn).toBeDisabled();
  });

  it("shows recording controls: timer, cancel, stop", () => {
    mockUseRecorder.mockReturnValue(makeRecorder({ phase: "recording", elapsed: 5 }));
    render(<MicButton onTranscript={vi.fn()} />);
    expect(screen.getByRole("group", { name: /recording controls/i })).toBeInTheDocument();
    expect(screen.getByText("0:05")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel recording/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /stop recording/i })).toBeInTheDocument();
  });

  it("calls stop() when stop button clicked", () => {
    const stop = vi.fn();
    mockUseRecorder.mockReturnValue(makeRecorder({ phase: "recording", elapsed: 3 }, { stop }));
    render(<MicButton onTranscript={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /stop recording/i }));
    expect(stop).toHaveBeenCalledTimes(1);
  });

  it("calls cancel() when cancel button clicked", () => {
    const cancel = vi.fn();
    mockUseRecorder.mockReturnValue(
      makeRecorder({ phase: "recording", elapsed: 10 }, { cancel }),
    );
    render(<MicButton onTranscript={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /cancel recording/i }));
    expect(cancel).toHaveBeenCalledTimes(1);
  });

  it("shows transcribing state as disabled mic button", () => {
    mockUseRecorder.mockReturnValue(makeRecorder({ phase: "transcribing" }));
    render(<MicButton onTranscript={vi.fn()} />);
    const btn = screen.getByRole("button", { name: /transcribing/i });
    expect(btn).toBeDisabled();
  });

  it("shows retry button in error state", () => {
    mockUseRecorder.mockReturnValue(
      makeRecorder({ phase: "error", message: "No speech detected." }),
    );
    render(<MicButton onTranscript={vi.fn()} />);
    expect(screen.getByRole("button", { name: /retry transcription/i })).toBeInTheDocument();
  });

  it("calls retry() when retry button clicked", () => {
    const retry = vi.fn();
    mockUseRecorder.mockReturnValue(
      makeRecorder({ phase: "error", message: "Failed." }, { retry }),
    );
    render(<MicButton onTranscript={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /retry transcription/i }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("shows denied state as disabled mic button", () => {
    mockUseRecorder.mockReturnValue(makeRecorder({ phase: "denied" }));
    render(<MicButton onTranscript={vi.fn()} />);
    const btn = screen.getByRole("button", { name: /microphone access denied/i });
    expect(btn).toBeDisabled();
  });

  it("disabled prop disables idle mic button", () => {
    mockUseRecorder.mockReturnValue(makeRecorder({ phase: "idle" }));
    render(<MicButton onTranscript={vi.fn()} disabled />);
    const btn = screen.getByRole("button", { name: /start voice recording/i });
    expect(btn).toBeDisabled();
  });

  it("formats elapsed time as mm:ss", () => {
    mockUseRecorder.mockReturnValue(makeRecorder({ phase: "recording", elapsed: 75 }));
    render(<MicButton onTranscript={vi.fn()} />);
    expect(screen.getByText("1:15")).toBeInTheDocument();
  });
});

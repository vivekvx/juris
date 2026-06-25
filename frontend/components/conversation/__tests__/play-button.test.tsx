import { render, screen, fireEvent } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import React from "react";
import { PlayButton } from "../play-button";
import type { UseAudioPlayerReturn, AudioPhase } from "@/hooks/use-audio-player";

vi.mock("@/hooks/use-audio-player", () => ({ useAudioPlayer: vi.fn() }));

import { useAudioPlayer } from "@/hooks/use-audio-player";

function makePlayer(
  phase: AudioPhase,
  overrides?: Partial<UseAudioPlayerReturn>,
): UseAudioPlayerReturn {
  return {
    phase,
    errorMessage: null,
    play: vi.fn(),
    stop: vi.fn(),
    ...overrides,
  };
}

const mockUseAudioPlayer = vi.mocked(useAudioPlayer);

beforeEach(() => { vi.clearAllMocks(); });

describe("PlayButton", () => {
  it("renders play button in idle state", () => {
    mockUseAudioPlayer.mockReturnValue(makePlayer("idle"));
    render(<PlayButton messageId="m1" text="Hello" />);
    expect(screen.getByRole("button", { name: /play audio/i })).toBeInTheDocument();
  });

  it("calls play() on click in idle state", () => {
    const play = vi.fn();
    mockUseAudioPlayer.mockReturnValue(makePlayer("idle", { play }));
    render(<PlayButton messageId="m1" text="Hello" />);
    fireEvent.click(screen.getByRole("button", { name: /play audio/i }));
    expect(play).toHaveBeenCalledOnce();
  });

  it("shows disabled spinner in loading state", () => {
    mockUseAudioPlayer.mockReturnValue(makePlayer("loading"));
    render(<PlayButton messageId="m1" text="Hello" />);
    expect(screen.getByRole("button", { name: /generating audio/i })).toBeDisabled();
  });

  it("shows stop button in playing state", () => {
    mockUseAudioPlayer.mockReturnValue(makePlayer("playing"));
    render(<PlayButton messageId="m1" text="Hello" />);
    expect(screen.getByRole("button", { name: /stop playback/i })).toBeInTheDocument();
  });

  it("calls stop() on click in playing state", () => {
    const stop = vi.fn();
    mockUseAudioPlayer.mockReturnValue(makePlayer("playing", { stop }));
    render(<PlayButton messageId="m1" text="Hello" />);
    fireEvent.click(screen.getByRole("button", { name: /stop playback/i }));
    expect(stop).toHaveBeenCalledOnce();
  });

  it("shows retry button in error state", () => {
    mockUseAudioPlayer.mockReturnValue(
      makePlayer("error", { errorMessage: "Service unavailable." }),
    );
    render(<PlayButton messageId="m1" text="Hello" />);
    expect(screen.getByRole("button", { name: /audio failed.*retry/i })).toBeInTheDocument();
  });

  it("calls play() again on retry click", () => {
    const play = vi.fn();
    mockUseAudioPlayer.mockReturnValue(
      makePlayer("error", { play, errorMessage: "Failed." }),
    );
    render(<PlayButton messageId="m1" text="Hello" />);
    fireEvent.click(screen.getByRole("button", { name: /audio failed.*retry/i }));
    expect(play).toHaveBeenCalledOnce();
  });

  it("passes messageId and text to useAudioPlayer", () => {
    mockUseAudioPlayer.mockReturnValue(makePlayer("idle"));
    render(<PlayButton messageId="msg-42" text="Legal question" />);
    expect(mockUseAudioPlayer).toHaveBeenCalledWith("msg-42", "Legal question");
  });
});

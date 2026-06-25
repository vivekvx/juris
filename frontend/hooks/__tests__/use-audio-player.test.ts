import { renderHook, act } from "@testing-library/react";
import { vi, describe, it, expect, beforeAll, beforeEach, afterAll, afterEach } from "vitest";
import { useAudioPlayer, _audioCache } from "../use-audio-player";

vi.mock("@/lib/firebase", () => ({
  getAuth: () => ({ currentUser: { getIdToken: async () => "test-token" } }),
}));

vi.mock("@/lib/api", () => ({ synthesizeAudio: vi.fn() }));

import { synthesizeAudio } from "@/lib/api";

// ── Mock Audio ─────────────────────────────────────────────────────────────
// Plain function declaration (not vi.fn, not arrow) so `new Audio()` always
// works — vi.fn creates a non-constructable arrow wrapper in this vitest env.

const mockPlay = vi.fn();
const mockPause = vi.fn();
let onendedCb: (() => void) | null = null;
let onerrorCb: (() => void) | null = null;

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function FakeAudio(_url?: string) {
  return {
    play: mockPlay,
    pause: mockPause,
    get onended() { return onendedCb; },
    set onended(v: (() => void) | null) { onendedCb = v; },
    get onerror() { return onerrorCb; },
    set onerror(v: (() => void) | null) { onerrorCb = v; },
  };
}

beforeAll(() => {
  vi.stubGlobal("Audio", FakeAudio);
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:mock-url"),
    revokeObjectURL: vi.fn(),
  });
});

beforeEach(() => {
  _audioCache.clear();
  onendedCb = null;
  onerrorCb = null;
  mockPlay.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.clearAllMocks();
});

afterAll(() => {
  vi.unstubAllGlobals();
});

// ── Tests ──────────────────────────────────────────────────────────────────

describe("useAudioPlayer", () => {
  it("starts in idle phase", () => {
    const { result } = renderHook(() => useAudioPlayer("msg-1", "Hello"));
    expect(result.current.phase).toBe("idle");
    expect(result.current.errorMessage).toBeNull();
  });

  it("play() transitions to loading then playing", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    const { result } = renderHook(() => useAudioPlayer("msg-2", "Hello"));

    await act(async () => { result.current.play(); });

    expect(result.current.phase).toBe("playing");
    expect(mockPlay).toHaveBeenCalledOnce();
  });

  it("shows loading while synthesis is in-flight", async () => {
    let resolveAudio!: (b: Blob) => void;
    vi.mocked(synthesizeAudio).mockReturnValueOnce(
      new Promise<Blob>((r) => { resolveAudio = r; }),
    );
    const { result } = renderHook(() => useAudioPlayer("msg-3", "Hello"));

    await act(async () => { result.current.play(); });
    expect(result.current.phase).toBe("loading");

    await act(async () => {
      resolveAudio(new Blob(["audio"]));
      await Promise.resolve();
    });
    expect(result.current.phase).toBe("playing");
  });

  it("audio ending naturally returns to idle", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    const { result } = renderHook(() => useAudioPlayer("msg-4", "Hello"));

    await act(async () => { result.current.play(); });
    await act(async () => { onendedCb?.(); });

    expect(result.current.phase).toBe("idle");
  });

  it("stop() returns to idle and pauses audio", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    const { result } = renderHook(() => useAudioPlayer("msg-5", "Hello"));

    await act(async () => { result.current.play(); });
    await act(async () => { result.current.stop(); });

    expect(result.current.phase).toBe("idle");
    expect(mockPause).toHaveBeenCalledOnce();
  });

  it("synthesis error sets error phase with message", async () => {
    vi.mocked(synthesizeAudio).mockRejectedValueOnce(
      new Error("Text-to-speech service is temporarily unavailable."),
    );
    const { result } = renderHook(() => useAudioPlayer("msg-6", "Hello"));

    await act(async () => { result.current.play(); });
    await act(async () => { await Promise.resolve(); });

    expect(result.current.phase).toBe("error");
    expect(result.current.errorMessage).toContain("unavailable");
  });

  it("playing a second message stops the first", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValue(new Blob(["audio"]));

    const { result: r1 } = renderHook(() => useAudioPlayer("msg-a", "Text A"));
    const { result: r2 } = renderHook(() => useAudioPlayer("msg-b", "Text B"));

    await act(async () => { r1.current.play(); });
    expect(r1.current.phase).toBe("playing");

    await act(async () => { r2.current.play(); });
    expect(r1.current.phase).toBe("idle");
    expect(r2.current.phase).toBe("playing");
  });

  it("replays use cached objectURL without calling synthesizeAudio again", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    const { result } = renderHook(() => useAudioPlayer("msg-7", "Hello"));

    await act(async () => { result.current.play(); });
    await act(async () => { onendedCb?.(); });

    // Second play — cache hit, no new network call
    await act(async () => { result.current.play(); });

    expect(synthesizeAudio).toHaveBeenCalledTimes(1);
    expect(result.current.phase).toBe("playing");
  });

  it("audio onerror sets error phase", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    const { result } = renderHook(() => useAudioPlayer("msg-8", "Hello"));

    await act(async () => { result.current.play(); });
    await act(async () => { onerrorCb?.(); });

    expect(result.current.phase).toBe("error");
    expect(result.current.errorMessage).toContain("Playback failed");
  });
});

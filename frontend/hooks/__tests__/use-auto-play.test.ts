import { renderHook, act } from "@testing-library/react";
import { vi, describe, it, expect, beforeAll, beforeEach, afterAll, afterEach } from "vitest";
import { useAutoPlay } from "../use-auto-play";

vi.mock("@/lib/firebase", () => ({
  getAuth: () => ({ currentUser: { getIdToken: async () => "test-token" } }),
}));

vi.mock("@/lib/api", () => ({ synthesizeAudio: vi.fn() }));

// vi.hoisted creates the Map before vi.mock hoisting so the factory can reference it
const sharedCache = vi.hoisted(() => new Map<string, string>());
vi.mock("@/hooks/use-audio-player", () => ({
  _audioCache: sharedCache,
  STOP_EVENT: "juris:audio-stop",
}));

import { synthesizeAudio } from "@/lib/api";

// ── FakeAudio (same pattern as use-audio-player tests) ─────────────────────

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
  sharedCache.clear();
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

describe("useAutoPlay", () => {
  it("does nothing when target is null", () => {
    renderHook(() => useAutoPlay(null, vi.fn()));
    expect(synthesizeAudio).not.toHaveBeenCalled();
  });

  it("synthesizes and plays audio when target is set", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    const onConsumed = vi.fn();

    renderHook(() => useAutoPlay({ id: "msg-1", content: "Hello" }, onConsumed));

    await act(async () => { await Promise.resolve(); });

    expect(synthesizeAudio).toHaveBeenCalledOnce();
    expect(mockPlay).toHaveBeenCalledOnce();
  });

  it("calls onConsumed immediately on first trigger", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    const onConsumed = vi.fn();

    renderHook(() => useAutoPlay({ id: "msg-2", content: "Hi" }, onConsumed));

    // onConsumed fires synchronously before async synthesis completes
    expect(onConsumed).toHaveBeenCalledOnce();
  });

  it("uses cached objectURL — no second synthesize call", async () => {
    sharedCache.set("msg-3", "blob:existing-url");

    renderHook(() => useAutoPlay({ id: "msg-3", content: "Hello" }, vi.fn()));

    await act(async () => { await Promise.resolve(); });

    expect(synthesizeAudio).not.toHaveBeenCalled();
    expect(mockPlay).toHaveBeenCalledOnce();
  });

  it("dispatches STOP_EVENT before playing to enforce mutual exclusion", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    const stopped: string[] = [];
    const listener = (e: Event) => {
      stopped.push((e as CustomEvent<{ except: string }>).detail.except);
    };
    window.addEventListener("juris:audio-stop", listener);

    renderHook(() => useAutoPlay({ id: "msg-4", content: "Hello" }, vi.fn()));
    await act(async () => { await Promise.resolve(); });

    expect(stopped).toContain("msg-4");
    window.removeEventListener("juris:audio-stop", listener);
  });

  it("stops audio when STOP_EVENT fires for a different id", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    renderHook(() => useAutoPlay({ id: "msg-5", content: "Hello" }, vi.fn()));
    await act(async () => { await Promise.resolve(); });

    mockPause.mockClear(); // baseline: only count pauses from the event below
    act(() => {
      window.dispatchEvent(
        new CustomEvent("juris:audio-stop", { detail: { except: "other-msg" } }),
      );
    });

    expect(mockPause).toHaveBeenCalledOnce();
  });

  it("does not stop audio when STOP_EVENT fires for its own id", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    renderHook(() => useAutoPlay({ id: "msg-6", content: "Hello" }, vi.fn()));
    await act(async () => { await Promise.resolve(); });

    mockPause.mockClear(); // baseline
    act(() => {
      window.dispatchEvent(
        new CustomEvent("juris:audio-stop", { detail: { except: "msg-6" } }),
      );
    });

    expect(mockPause).not.toHaveBeenCalled();
  });

  it("handles synthesis failure silently — no error thrown", async () => {
    vi.mocked(synthesizeAudio).mockRejectedValueOnce(new Error("503 Service Unavailable"));
    const onConsumed = vi.fn();

    renderHook(() => useAutoPlay({ id: "msg-7", content: "Hello" }, onConsumed));
    await act(async () => { await Promise.resolve(); });

    expect(onConsumed).toHaveBeenCalledOnce();
    expect(mockPlay).not.toHaveBeenCalled();
  });

  it("handles mobile autoplay block gracefully — no error thrown", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    mockPlay.mockRejectedValueOnce(new DOMException("play() failed", "NotAllowedError"));

    renderHook(() => useAutoPlay({ id: "msg-8", content: "Hello" }, vi.fn()));
    await act(async () => { await Promise.resolve(); });

    expect(mockPlay).toHaveBeenCalledOnce();
  });

  it("stops audio on unmount (navigation away)", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValueOnce(new Blob(["audio"]));
    const { unmount } = renderHook(() =>
      useAutoPlay({ id: "msg-9", content: "Hello" }, vi.fn()),
    );
    await act(async () => { await Promise.resolve(); });

    mockPause.mockClear(); // baseline: only count the unmount pause
    unmount();

    expect(mockPause).toHaveBeenCalledOnce();
  });

  it("does not replay same message id if target prop reference changes", async () => {
    vi.mocked(synthesizeAudio).mockResolvedValue(new Blob(["audio"]));

    let target = { id: "msg-10", content: "Hello" };
    const { rerender } = renderHook(
      ({ t }: { t: typeof target }) => useAutoPlay(t, vi.fn()),
      { initialProps: { t: target } },
    );
    await act(async () => { await Promise.resolve(); });

    target = { id: "msg-10", content: "Hello" }; // same id, new reference
    rerender({ t: target });
    await act(async () => { await Promise.resolve(); });

    expect(synthesizeAudio).toHaveBeenCalledTimes(1);
  });
});

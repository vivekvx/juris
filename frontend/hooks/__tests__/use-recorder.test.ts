import { renderHook, act } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { useRecorder } from "../use-recorder";

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

vi.mock("@/lib/firebase", () => ({
  getAuth: () => ({ currentUser: { getIdToken: async () => "test-token" } }),
}));

vi.mock("@/lib/api", () => ({
  transcribeAudio: vi.fn(),
}));

import { transcribeAudio } from "@/lib/api";

// ── MockMediaRecorder ──────────────────────────────────────────────────────

type DataAvailableHandler = (e: { data: Blob }) => void;

let capturedMR: {
  state: "inactive" | "recording";
  ondataavailable: DataAvailableHandler | null;
  onstop: (() => void) | null;
  start: ReturnType<typeof vi.fn>;
  stop: ReturnType<typeof vi.fn>;
} | null = null;

class MockMediaRecorder {
  static isTypeSupported = vi.fn(() => true);
  state: "inactive" | "recording" = "inactive";
  ondataavailable: DataAvailableHandler | null = null;
  onstop: (() => void) | null = null;

  start = vi.fn(() => { this.state = "recording"; });
  stop = vi.fn(() => {
    this.state = "inactive";
    this.onstop?.();
  });

  constructor(_stream: MediaStream, _opts?: MediaRecorderOptions) {
    capturedMR = this;
  }
}

const mockStream = {
  getTracks: () => [{ stop: vi.fn() }],
} as unknown as MediaStream;

// ── Setup ──────────────────────────────────────────────────────────────────

beforeEach(() => {
  capturedMR = null;
  vi.stubGlobal("MediaRecorder", MockMediaRecorder);
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia: vi.fn().mockResolvedValue(mockStream) },
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

// ── Tests ──────────────────────────────────────────────────────────────────

describe("useRecorder", () => {
  it("starts in idle phase", () => {
    const { result } = renderHook(() => useRecorder(vi.fn()));
    expect(result.current.recorderState.phase).toBe("idle");
  });

  it("transitions idle → recording on start()", async () => {
    const { result } = renderHook(() => useRecorder(vi.fn()));

    await act(async () => {
      result.current.start();
    });

    expect(result.current.recorderState.phase).toBe("recording");
    expect(capturedMR?.start).toHaveBeenCalledWith(100);
  });

  it("transitions to denied when getUserMedia rejects", async () => {
    (navigator.mediaDevices.getUserMedia as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("Permission denied"),
    );

    const { result } = renderHook(() => useRecorder(vi.fn()));

    await act(async () => {
      result.current.start();
    });

    expect(result.current.recorderState.phase).toBe("denied");
  });

  it("stop() triggers transcription and calls onTranscript on success", async () => {
    const mockTranscribeAudio = vi.mocked(transcribeAudio);

    // Deferred promise so we can observe the "transcribing" phase before resolution
    let resolveTranscribe!: (v: Awaited<ReturnType<typeof transcribeAudio>>) => void;
    const deferred = new Promise<Awaited<ReturnType<typeof transcribeAudio>>>(
      (res) => { resolveTranscribe = res; },
    );
    mockTranscribeAudio.mockReturnValueOnce(deferred);

    const onTranscript = vi.fn();
    const { result } = renderHook(() => useRecorder(onTranscript));

    await act(async () => { result.current.start(); });
    expect(result.current.recorderState.phase).toBe("recording");

    // stop() → onstop fires → runTranscribe starts (deferred)
    await act(async () => { result.current.stop(); });
    expect(result.current.recorderState.phase).toBe("transcribing");

    // resolve and drain
    await act(async () => {
      resolveTranscribe({ text: "Hello world", language: "en-IN", duration_ms: 1500, confidence: 0.95 });
      await Promise.resolve();
    });

    expect(result.current.recorderState.phase).toBe("idle");
    expect(onTranscript).toHaveBeenCalledWith("Hello world");
    expect(mockTranscribeAudio).toHaveBeenCalledWith(expect.any(Blob), "test-token");
  });

  it("cancel() returns to idle without transcribing", async () => {
    const mockTranscribeAudio = vi.mocked(transcribeAudio);
    const { result } = renderHook(() => useRecorder(vi.fn()));

    await act(async () => { result.current.start(); });
    expect(result.current.recorderState.phase).toBe("recording");

    await act(async () => { result.current.cancel(); });

    expect(result.current.recorderState.phase).toBe("idle");
    expect(mockTranscribeAudio).not.toHaveBeenCalled();
  });

  it("transcription error sets error phase and allows retry", async () => {
    const mockTranscribeAudio = vi.mocked(transcribeAudio);

    // First call fails
    let rejectFirst!: (e: Error) => void;
    const firstCall = new Promise<never>((_, rej) => { rejectFirst = rej; });
    mockTranscribeAudio.mockReturnValueOnce(firstCall);

    // Second call succeeds
    let resolveSecond!: (v: Awaited<ReturnType<typeof transcribeAudio>>) => void;
    const secondCall = new Promise<Awaited<ReturnType<typeof transcribeAudio>>>(
      (res) => { resolveSecond = res; },
    );
    mockTranscribeAudio.mockReturnValueOnce(secondCall);

    const onTranscript = vi.fn();
    const { result } = renderHook(() => useRecorder(onTranscript));

    await act(async () => { result.current.start(); });
    await act(async () => { result.current.stop(); });

    // Reject first call → error phase
    await act(async () => {
      rejectFirst(new Error("No speech detected. Please try again."));
      await Promise.resolve();
    });

    expect(result.current.recorderState.phase).toBe("error");
    if (result.current.recorderState.phase === "error") {
      expect(result.current.recorderState.message).toContain("No speech detected");
    }

    // Retry → resolve second call
    await act(async () => { result.current.retry(); });
    await act(async () => {
      resolveSecond({ text: "Retry success", language: "en-IN", duration_ms: 800, confidence: 0.9 });
      await Promise.resolve();
    });

    expect(result.current.recorderState.phase).toBe("idle");
    expect(onTranscript).toHaveBeenCalledWith("Retry success");
  });

  it("dispatches juris:audio-stop when recording starts (stops active playback)", async () => {
    const stopped: string[] = [];
    const listener = (e: Event) =>
      stopped.push((e as CustomEvent<{ except: string }>).detail.except);
    window.addEventListener("juris:audio-stop", listener);

    const { result } = renderHook(() => useRecorder(vi.fn()));
    await act(async () => { result.current.start(); });

    expect(stopped.length).toBeGreaterThan(0);
    window.removeEventListener("juris:audio-stop", listener);
  });

  it("stop() when not recording goes to idle without transcribing", async () => {
    const mockTranscribeAudio = vi.mocked(transcribeAudio);
    const { result } = renderHook(() => useRecorder(vi.fn()));

    await act(async () => { result.current.stop(); });

    expect(result.current.recorderState.phase).toBe("idle");
    expect(mockTranscribeAudio).not.toHaveBeenCalled();
  });
});

"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { toast } from "sonner";
import { getAuth } from "@/lib/firebase";
import { transcribeAudio } from "@/lib/api";
import { STOP_EVENT } from "@/hooks/use-audio-player";

export type RecorderState =
  | { phase: "idle" }
  | { phase: "requesting" }
  | { phase: "denied" }
  | { phase: "recording"; elapsed: number }
  | { phase: "transcribing" }
  | { phase: "error"; message: string };

export type UseRecorderReturn = {
  recorderState: RecorderState;
  start: () => void;
  stop: () => void;
  cancel: () => void;
  retry: () => void;
};

export function useRecorder(onTranscript: (text: string) => void): UseRecorderReturn {
  const [recorderState, setRecorderState] = useState<RecorderState>({ phase: "idle" });

  const mrRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastBlobRef = useRef<Blob | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  useEffect(() => { onTranscriptRef.current = onTranscript; }, [onTranscript]);

  const cleanup = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    mrRef.current = null;
    chunksRef.current = [];
  }, []);

  useEffect(() => () => cleanup(), [cleanup]);

  const runTranscribe = useCallback(async (blob: Blob) => {
    lastBlobRef.current = blob;
    setRecorderState({ phase: "transcribing" });
    try {
      const user = getAuth().currentUser;
      if (!user) throw new Error("Not authenticated.");
      const idToken = await user.getIdToken();
      const result = await transcribeAudio(blob, idToken);
      setRecorderState({ phase: "idle" });
      onTranscriptRef.current(result.text);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Transcription failed. Please try again.";
      toast.error(message);
      setRecorderState({ phase: "error", message });
    }
  }, []);

  const start = useCallback(() => {
    void (async () => {
      // Stop any active audio playback before recording
      window.dispatchEvent(new CustomEvent(STOP_EVENT, { detail: { except: "" } }));
      setRecorderState({ phase: "requesting" });

      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch {
        setRecorderState({ phase: "denied" });
        return;
      }

      streamRef.current = stream;
      chunksRef.current = [];

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const mr = new MediaRecorder(stream, { mimeType });
      mrRef.current = mr;

      mr.ondataavailable = (e: BlobEvent) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        cleanup();
        void runTranscribe(blob);
      };

      mr.start(100);
      setRecorderState({ phase: "recording", elapsed: 0 });

      let secs = 0;
      timerRef.current = setInterval(() => {
        secs += 1;
        setRecorderState({ phase: "recording", elapsed: secs });
        // Auto-stop at 120 s max
        if (secs >= 120 && mrRef.current?.state === "recording") {
          if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
          mrRef.current.stop();
        }
      }, 1000);
    })();
  }, [cleanup, runTranscribe]);

  const stop = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (mrRef.current?.state === "recording") {
      mrRef.current.stop(); // triggers onstop → runTranscribe
    } else {
      cleanup();
      setRecorderState({ phase: "idle" });
    }
  }, [cleanup]);

  const cancel = useCallback(() => {
    // Detach onstop so stop() won't trigger transcription
    if (mrRef.current) mrRef.current.onstop = null;
    cleanup();
    setRecorderState({ phase: "idle" });
  }, [cleanup]);

  const retry = useCallback(() => {
    if (lastBlobRef.current) void runTranscribe(lastBlobRef.current);
  }, [runTranscribe]);

  return { recorderState, start, stop, cancel, retry };
}

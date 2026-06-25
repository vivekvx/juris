"use client";
import { useState, useCallback, useEffect, useRef } from "react";
import { getAuth } from "@/lib/firebase";
import { synthesizeAudio } from "@/lib/api";

export type AudioPhase = "idle" | "loading" | "playing" | "error";

export type UseAudioPlayerReturn = {
  phase: AudioPhase;
  errorMessage: string | null;
  play: () => void;
  stop: () => void;
};

// Module-level cache: messageId → objectURL (session-scoped, survives re-renders)
export const _audioCache = new Map<string, string>();
export const STOP_EVENT = "juris:audio-stop";

export function useAudioPlayer(messageId: string, text: string): UseAudioPlayerReturn {
  const [phase, setPhase] = useState<AudioPhase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPhase("idle");
    setErrorMessage(null);
  }, []);

  // Stop when another message starts playing
  useEffect(() => {
    function handleStop(e: Event) {
      const { except } = (e as CustomEvent<{ except: string }>).detail;
      if (except !== messageId) stop();
    }
    window.addEventListener(STOP_EVENT, handleStop as EventListener);
    return () => window.removeEventListener(STOP_EVENT, handleStop as EventListener);
  }, [messageId, stop]);

  // Cleanup audio on unmount
  useEffect(() => () => {
    if (audioRef.current) {
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.pause();
    }
  }, []);

  const play = useCallback(() => {
    void (async () => {
      // Stop all other players
      window.dispatchEvent(new CustomEvent(STOP_EVENT, { detail: { except: messageId } }));

      setPhase("loading");
      setErrorMessage(null);

      try {
        let objectUrl = _audioCache.get(messageId);

        if (!objectUrl) {
          const user = getAuth().currentUser;
          if (!user) throw new Error("Not authenticated.");
          const idToken = await user.getIdToken();
          const blob = await synthesizeAudio(text, idToken);
          objectUrl = URL.createObjectURL(blob);
          _audioCache.set(messageId, objectUrl);
        }

        const audio = new Audio(objectUrl);
        audioRef.current = audio;

        audio.onended = () => {
          audioRef.current = null;
          setPhase("idle");
        };

        audio.onerror = () => {
          audioRef.current = null;
          setPhase("error");
          setErrorMessage("Playback failed. Try again.");
        };

        await audio.play();
        setPhase("playing");
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Audio generation failed.";
        setErrorMessage(msg);
        setPhase("error");
      }
    })();
  }, [messageId, text]);

  return { phase, errorMessage, play, stop };
}

"use client";
import { useEffect, useRef } from "react";
import { getAuth } from "@/lib/firebase";
import { synthesizeAudio } from "@/lib/api";
import { _audioCache, STOP_EVENT } from "@/hooks/use-audio-player";
import type { AutoPlayTarget } from "@/hooks/use-conversation";

export function useAutoPlay(target: AutoPlayTarget | null, onConsumed: () => void): void {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  // Track which message ID was already triggered to prevent double-play on re-renders
  const consumedRef = useRef<string | null>(null);
  const onConsumedRef = useRef(onConsumed);
  useEffect(() => { onConsumedRef.current = onConsumed; }, [onConsumed]);

  // Stop auto-played audio on unmount (navigation away)
  useEffect(
    () => () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    },
    [],
  );

  // Respect mutual-exclusion events — another audio player took over
  useEffect(() => {
    function handle(e: Event) {
      const { except } = (e as CustomEvent<{ except: string }>).detail;
      if (consumedRef.current && except !== consumedRef.current && audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    }
    window.addEventListener(STOP_EVENT, handle as EventListener);
    return () => window.removeEventListener(STOP_EVENT, handle as EventListener);
  }, []);

  useEffect(() => {
    if (!target || consumedRef.current === target.id) return;

    consumedRef.current = target.id;
    // Clear parent state immediately so re-renders don't re-trigger
    onConsumedRef.current();

    void (async () => {
      // Signal all other players to stop
      window.dispatchEvent(new CustomEvent(STOP_EVENT, { detail: { except: target.id } }));

      try {
        let objectUrl = _audioCache.get(target.id);
        if (!objectUrl) {
          const user = getAuth().currentUser;
          if (!user) return;
          const idToken = await user.getIdToken();
          const blob = await synthesizeAudio(target.content, idToken);
          objectUrl = URL.createObjectURL(blob);
          _audioCache.set(target.id, objectUrl);
        }

        const audio = new Audio(objectUrl);
        audioRef.current = audio;
        audio.onended = () => { audioRef.current = null; };
        audio.onerror = () => { audioRef.current = null; };

        // Best-effort: mobile browsers block autoplay without a prior user gesture.
        // Silent catch — the PlayButton remains available as the reliable path.
        await audio.play().catch(() => { audioRef.current = null; });
      } catch {
        // Synthesis failure — silent, PlayButton on the message is always present
      }
    })();
  }, [target]);
}

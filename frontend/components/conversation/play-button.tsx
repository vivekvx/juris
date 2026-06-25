"use client";
import { Play, Stop, CircleNotch, WarningCircle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { useAudioPlayer } from "@/hooks/use-audio-player";

export function PlayButton({
  messageId,
  text,
}: {
  messageId: string;
  text: string;
}) {
  const { phase, errorMessage, play, stop } = useAudioPlayer(messageId, text);

  if (phase === "loading") {
    return (
      <Button
        size="icon-xs"
        variant="ghost"
        disabled
        className="h-6 w-6 text-muted-foreground"
        aria-label="Generating audio…"
      >
        <CircleNotch size={13} className="animate-spin" />
      </Button>
    );
  }

  if (phase === "playing") {
    return (
      <Button
        size="icon-xs"
        variant="ghost"
        onClick={stop}
        className="h-6 w-6 text-primary hover:text-primary hover:bg-primary/10"
        aria-label="Stop playback"
      >
        <Stop size={13} weight="fill" />
      </Button>
    );
  }

  if (phase === "error") {
    return (
      <Button
        size="icon-xs"
        variant="ghost"
        onClick={play}
        className="h-6 w-6 text-destructive hover:text-destructive hover:bg-destructive/10"
        aria-label="Audio failed — retry"
        title={errorMessage ?? "Audio generation failed."}
      >
        <WarningCircle size={13} />
      </Button>
    );
  }

  return (
    <Button
      size="icon-xs"
      variant="ghost"
      onClick={play}
      className="h-6 w-6 text-muted-foreground/50 hover:text-muted-foreground transition-colors"
      aria-label="Play audio"
    >
      <Play size={13} weight="fill" />
    </Button>
  );
}

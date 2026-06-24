"use client";
import { Microphone, Stop, X, ArrowClockwise } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { useRecorder } from "@/hooks/use-recorder";

function formatElapsed(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function MicButton({
  onTranscript,
  disabled = false,
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}) {
  const { recorderState, start, stop, cancel, retry } = useRecorder(onTranscript);
  const { phase } = recorderState;

  if (phase === "recording") {
    return (
      <div
        className="flex items-center gap-1.5 flex-shrink-0"
        role="group"
        aria-label="Recording controls"
      >
        <span
          className="text-xs tabular-nums text-destructive font-mono min-w-[32px] select-none"
          aria-live="polite"
          aria-label={`Recording: ${formatElapsed(recorderState.elapsed)}`}
        >
          {formatElapsed(recorderState.elapsed)}
        </span>
        <Button
          size="icon-sm"
          variant="ghost"
          onClick={cancel}
          className="h-8 w-8"
          aria-label="Cancel recording"
        >
          <X size={14} />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={stop}
          className="flex-shrink-0 h-11 w-11 text-destructive hover:text-destructive hover:bg-destructive/15 border border-destructive/40"
          aria-label="Stop recording"
        >
          <Stop size={18} weight="fill" />
        </Button>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <Button
        size="icon"
        variant="ghost"
        onClick={retry}
        className="flex-shrink-0 h-11 w-11 text-destructive hover:text-destructive hover:bg-destructive/10"
        aria-label="Retry transcription"
        title={(recorderState as { phase: "error"; message: string }).message}
      >
        <ArrowClockwise size={18} />
      </Button>
    );
  }

  return (
    <Button
      size="icon"
      variant="ghost"
      onClick={phase === "idle" ? start : undefined}
      disabled={
        disabled ||
        phase === "requesting" ||
        phase === "transcribing" ||
        phase === "denied"
      }
      className="flex-shrink-0 h-11 w-11"
      aria-label={
        phase === "requesting"
          ? "Requesting microphone…"
          : phase === "transcribing"
            ? "Transcribing…"
            : phase === "denied"
              ? "Microphone access denied"
              : "Start voice recording"
      }
      title={
        phase === "denied"
          ? "Microphone access denied. Check browser settings."
          : undefined
      }
    >
      <Microphone
        size={18}
        className={
          phase === "requesting" || phase === "transcribing"
            ? "animate-pulse text-primary"
            : phase === "denied"
              ? "text-destructive"
              : ""
        }
      />
    </Button>
  );
}

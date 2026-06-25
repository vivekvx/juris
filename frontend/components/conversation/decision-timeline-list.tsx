"use client";
import { useState } from "react";
import { ShieldCheck } from "@phosphor-icons/react";
import { Skeleton } from "@/components/ui/skeleton";
import { useDecisionTimeline } from "@/hooks/use-decision-timeline";
import { DecisionDetailDrawer } from "@/components/conversation/decision-detail-drawer";
import { cn } from "@/lib/utils";
import type { LedgerEntryResponse, LedgerEntryKind } from "@/types/ledger";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

function KindBadge({ kind }: { kind: LedgerEntryKind }) {
  const styles: Record<LedgerEntryKind, string> = {
    decision: "bg-primary/10 text-primary",
    annotation: "bg-amber-500/10 text-amber-400",
    override: "bg-destructive/10 text-destructive",
  };
  return (
    <span
      className={cn(
        "text-[0.55rem] font-medium px-1.5 py-0.5 rounded-sm uppercase tracking-wide flex-shrink-0",
        styles[kind],
      )}
    >
      {kind}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Timeline row
// ---------------------------------------------------------------------------

function TimelineRow({
  entry,
  onClick,
}: {
  entry: LedgerEntryResponse;
  onClick: () => void;
}) {
  const isDecision = entry.kind === "decision";
  const citationCount = entry.retrieval?.citations.length ?? 0;
  const sourcesUsed = entry.output?.sources_used ?? false;
  const isOverride = entry.kind === "override";

  return (
    <button
      onClick={onClick}
      type="button"
      className="w-full text-left px-4 py-2.5 hover:bg-secondary/40 transition-colors border-b border-border/40 last:border-0 focus-visible:outline-none focus-visible:bg-secondary/40"
    >
      <div className="flex items-start gap-2.5">
        {/* Sequence number */}
        <span
          className="text-[0.6rem] font-mono text-muted-foreground/40 w-5 flex-shrink-0 pt-0.5 text-right tabular-nums"
          aria-label={`Sequence ${entry.sequence_no}`}
        >
          {entry.sequence_no}
        </span>

        <div className="flex-1 min-w-0">
          {/* Kind + timestamp row */}
          <div className="flex items-center gap-1.5 mb-0.5">
            <KindBadge kind={entry.kind} />
            <span className="text-[0.6rem] text-muted-foreground/50 ml-auto flex-shrink-0 tabular-nums">
              {formatTime(entry.created_at)}
            </span>
          </div>

          {/* Primary content line */}
          {isDecision && entry.query ? (
            <p className="text-xs text-foreground/75 truncate leading-snug">
              {entry.query}
            </p>
          ) : isOverride ? (
            <p className="text-xs text-muted-foreground/70 truncate leading-snug italic">
              Human override
            </p>
          ) : (
            <p className="text-xs text-muted-foreground/70 truncate leading-snug italic">
              Annotation
            </p>
          )}

          {/* Grounding indicator */}
          {isDecision && (
            <div className="flex items-center gap-1 mt-1">
              {sourcesUsed ? (
                <span className="flex items-center gap-0.5 text-[0.6rem] text-emerald-500/70">
                  <ShieldCheck size={9} weight="fill" aria-hidden />
                  {citationCount} {citationCount === 1 ? "src" : "srcs"}
                </span>
              ) : (
                <span className="text-[0.6rem] text-muted-foreground/40">no sources</span>
              )}
            </div>
          )}
        </div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function TimelineSkeleton() {
  return (
    <div className="space-y-0">
      {[1, 2, 3].map((i) => (
        <div key={i} className="px-4 py-2.5 border-b border-border/40">
          <div className="flex gap-2.5">
            <Skeleton className="h-3 w-4 mt-0.5" />
            <div className="flex-1 space-y-1.5">
              <div className="flex items-center gap-1.5">
                <Skeleton className="h-3.5 w-14" />
                <Skeleton className="h-3 w-16 ml-auto" />
              </div>
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-2.5 w-12" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export function DecisionTimelineList({ conversationId }: { conversationId: string }) {
  const { state } = useDecisionTimeline(conversationId);
  const [selectedEntry, setSelectedEntry] = useState<LedgerEntryResponse | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  function handleEntryClick(entry: LedgerEntryResponse) {
    setSelectedEntry(entry);
    setDrawerOpen(true);
  }

  function handleClose() {
    setDrawerOpen(false);
  }

  return (
    <>
      <div className="flex-1 overflow-y-auto" role="list" aria-label="Decision timeline">
        {state.status === "loading" && <TimelineSkeleton />}

        {state.status === "error" && (
          <div className="px-4 py-8 text-center">
            <p className="text-xs text-muted-foreground">{state.message}</p>
          </div>
        )}

        {state.status === "ready" && state.entries.length === 0 && (
          <div className="px-4 py-10 text-center">
            <p className="text-xs text-muted-foreground">No decisions logged yet.</p>
            <p className="text-[0.65rem] text-muted-foreground/50 mt-1">
              Decisions appear here as the conversation progresses.
            </p>
          </div>
        )}

        {state.status === "ready" &&
          state.entries.map((entry) => (
            <div key={entry.id} role="listitem">
              <TimelineRow entry={entry} onClick={() => handleEntryClick(entry)} />
            </div>
          ))}
      </div>

      <DecisionDetailDrawer
        entry={selectedEntry}
        open={drawerOpen}
        onClose={handleClose}
      />
    </>
  );
}

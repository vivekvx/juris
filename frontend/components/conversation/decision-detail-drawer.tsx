"use client";
import { useState } from "react";
import { X, CaretDown } from "@phosphor-icons/react";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerClose,
} from "@/components/ui/drawer";
import { cn } from "@/lib/utils";
import type { LedgerEntryResponse, CachedCitation } from "@/types/ledger";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(iso));
}

function shortHash(hash: string): string {
  const colonIdx = hash.indexOf(":");
  if (colonIdx === -1) return hash.slice(0, 16) + "…";
  const prefix = hash.slice(0, colonIdx + 1);
  const hex = hash.slice(colonIdx + 1);
  return `${prefix}${hex.slice(0, 8)}…`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[0.6875rem] font-medium text-muted-foreground/60 uppercase tracking-widest mb-2">
      {children}
    </p>
  );
}

function KindBadge({ kind }: { kind: string }) {
  const styles: Record<string, string> = {
    decision: "bg-primary/10 text-primary",
    annotation: "bg-amber-500/10 text-amber-400",
    override: "bg-destructive/10 text-destructive",
  };
  return (
    <span
      className={cn(
        "text-[0.6rem] font-medium px-1.5 py-0.5 rounded-sm uppercase tracking-wide",
        styles[kind] ?? "bg-muted text-muted-foreground",
      )}
    >
      {kind}
    </span>
  );
}

function GroundingBadge({ sourcesUsed, count }: { sourcesUsed: boolean; count: number }) {
  if (sourcesUsed) {
    return (
      <span className="text-xs text-emerald-500 font-medium">
        Grounded · {count} {count === 1 ? "source" : "sources"}
      </span>
    );
  }
  return <span className="text-xs text-muted-foreground">No sources used</span>;
}

function CitationRow({ citation, index }: { citation: CachedCitation; index: number }) {
  return (
    <div className="flex items-start gap-2 py-1.5 border-b border-border/50 last:border-0">
      <span className="text-[0.6rem] font-mono text-muted-foreground/50 w-4 flex-shrink-0 pt-0.5">
        {index}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-foreground/80 truncate">{citation.original_filename}</p>
        <p className="text-[0.65rem] text-muted-foreground/60 font-mono">
          chunk {citation.chunk_index}
          {citation.page_number !== null ? ` · p.${citation.page_number}` : ""}
          {" · score "}
          {citation.score.toFixed(2)}
        </p>
      </div>
    </div>
  );
}

function CollapsibleHash({ label, value }: { label: string; value: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[0.6875rem] text-muted-foreground/70 hover:text-foreground/70 transition-colors"
        aria-expanded={open}
        type="button"
      >
        <CaretDown
          size={10}
          className={cn("transition-transform duration-150", open && "rotate-180")}
          aria-hidden
        />
        {label}
      </button>
      {open && (
        <p className="mt-1.5 text-[0.6rem] font-mono text-muted-foreground/60 break-all leading-relaxed pl-4">
          {value}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Drawer body
// ---------------------------------------------------------------------------

function DrawerBody({ entry }: { entry: LedgerEntryResponse }) {
  const isDecision = entry.kind === "decision";
  const citationCount = entry.retrieval?.citations.length ?? 0;

  return (
    <div className="flex-1 overflow-y-auto px-4 pb-6 space-y-5">
      {/* Grounding */}
      {isDecision && entry.output && (
        <section aria-label="Grounding">
          <SectionLabel>Grounding</SectionLabel>
          <GroundingBadge sourcesUsed={entry.output.sources_used} count={citationCount} />
          {entry.output.sources_used && (
            <div className="mt-0.5 text-[0.65rem] text-muted-foreground/60 font-mono">
              top score {entry.output.grounding.top_score.toFixed(3)}
            </div>
          )}
        </section>
      )}

      {/* Query */}
      {isDecision && entry.query && (
        <section aria-label="Query">
          <SectionLabel>Query</SectionLabel>
          <p className="text-sm text-foreground/90 leading-relaxed">{entry.query}</p>
        </section>
      )}

      {/* Model & Prompt */}
      {isDecision && entry.model && (
        <section aria-label="Model">
          <SectionLabel>Model</SectionLabel>
          <dl className="space-y-1">
            <div className="flex justify-between text-xs">
              <dt className="text-muted-foreground">Model</dt>
              <dd className="font-mono text-foreground/80">{entry.model.name}</dd>
            </div>
            <div className="flex justify-between text-xs">
              <dt className="text-muted-foreground">Prompt version</dt>
              <dd className="font-mono text-foreground/80">{entry.model.prompt_template_version}</dd>
            </div>
            <div className="flex justify-between text-xs">
              <dt className="text-muted-foreground">Temperature</dt>
              <dd className="font-mono text-foreground/80">{entry.model.temperature}</dd>
            </div>
          </dl>
        </section>
      )}

      {/* Citations */}
      {isDecision && entry.retrieval && entry.retrieval.citations.length > 0 && (
        <section aria-label="Sources retrieved">
          <SectionLabel>Sources retrieved ({citationCount})</SectionLabel>
          <div>
            {entry.retrieval.citations.map((c, i) => (
              <CitationRow key={`${c.doc_id}-${c.chunk_index}`} citation={c} index={i + 1} />
            ))}
          </div>
        </section>
      )}

      {/* Override fields */}
      {entry.kind === "override" && (
        <section aria-label="Human override">
          <SectionLabel>Human override</SectionLabel>
          <dl className="space-y-1">
            {entry.disposition && (
              <div className="flex justify-between text-xs">
                <dt className="text-muted-foreground">Disposition</dt>
                <dd className="font-medium text-foreground/80 capitalize">{entry.disposition}</dd>
              </div>
            )}
            {entry.reason && (
              <div className="text-xs">
                <dt className="text-muted-foreground mb-0.5">Reason</dt>
                <dd className="text-foreground/80 leading-snug">{entry.reason}</dd>
              </div>
            )}
          </dl>
        </section>
      )}

      {/* Annotation note */}
      {entry.kind === "annotation" && entry.note && (
        <section aria-label="Annotation">
          <SectionLabel>Annotation</SectionLabel>
          <p className="text-sm text-foreground/80 leading-relaxed">{entry.note}</p>
        </section>
      )}

      {/* Hash chain — collapsed by default */}
      <section aria-label="Integrity">
        <SectionLabel>Integrity</SectionLabel>
        <div className="space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Sequence</span>
            <span className="font-mono text-foreground/70">#{entry.sequence_no}</span>
          </div>
          <CollapsibleHash label="Entry hash" value={entry.entry_hash} />
          <CollapsibleHash label="Previous hash" value={entry.prev_hash} />
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export function DecisionDetailDrawer({
  entry,
  open,
  onClose,
}: {
  entry: LedgerEntryResponse | null;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Drawer open={open} onOpenChange={(o) => { if (!o) onClose(); }} direction="bottom">
      <DrawerContent className="max-h-[85vh] flex flex-col">
        <DrawerHeader className="flex-shrink-0 flex items-start justify-between border-b border-border pb-3">
          <div>
            <DrawerTitle className="text-sm font-medium">
              {entry ? `Decision #${entry.sequence_no}` : "Decision"}
            </DrawerTitle>
            {entry && (
              <div className="flex items-center gap-2 mt-1">
                <KindBadge kind={entry.kind} />
                <span className="text-[0.65rem] text-muted-foreground/60">
                  {formatTimestamp(entry.created_at)}
                </span>
                <span className="text-[0.65rem] font-mono text-muted-foreground/40 hidden sm:block">
                  {shortHash(entry.id)}
                </span>
              </div>
            )}
          </div>
          <DrawerClose
            className="flex-shrink-0 ml-2 mt-0.5 text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Close decision detail"
          >
            <X size={15} aria-hidden />
          </DrawerClose>
        </DrawerHeader>

        {entry ? (
          <DrawerBody entry={entry} />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-sm text-muted-foreground">No decision selected.</p>
          </div>
        )}
      </DrawerContent>
    </Drawer>
  );
}

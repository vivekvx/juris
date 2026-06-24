import type { Citation } from "@/types/conversation";

export function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  const loc = citation.page_number ? ` · page ${citation.page_number}` : "";
  return (
    <details className="group rounded-lg border border-border bg-muted/30 text-xs">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-1.5 text-muted-foreground hover:text-foreground">
        <span className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded bg-primary/15 text-[0.6rem] font-semibold text-primary">
          {index}
        </span>
        <span className="truncate font-medium">{citation.original_filename}{loc}</span>
        <span className="ml-auto flex-shrink-0 opacity-50 group-open:rotate-180 transition-transform">▾</span>
      </summary>
      <p className="border-t border-border px-3 py-2 text-muted-foreground leading-relaxed line-clamp-4">
        {citation.content}
      </p>
    </details>
  );
}

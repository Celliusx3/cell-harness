"use client";

import { useState } from "react";

import type { CompactionItem } from "@/lib/timeline";

/** ` · 12k tokens`, or the empty string. */
function tokenLabel(tokens: number | null): string {
  if (tokens === null) return "";
  if (tokens >= 1000) return ` · ${Math.round(tokens / 1000)}k tokens`;
  return ` · ${tokens} tokens`;
}

export function Compaction({ item }: { item: CompactionItem }) {
  const [open, setOpen] = useState(false);

  if (item.pending) {
    return (
      <p className="text-center text-xs text-ink-soft">
        Compacting the conversation to free up context…
      </p>
    );
  }

  if (item.summary === null) {
    return (
      <p className="text-center text-xs text-ink-soft">
        Could not compact the conversation{item.error ? ` (${item.error})` : ""}.
      </p>
    );
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        title={open ? "Hide the summary" : "Show the summary"}
        className="rounded-md border border-line bg-surface px-2 py-0.5 text-xs text-ink-soft transition hover:text-ink"
      >
        Conversation compacted{tokenLabel(item.tokens)}
      </button>
      {open ? (
        <pre className="max-h-96 w-full max-w-2xl overflow-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-surface-sunken p-3 font-mono text-xs">
          {item.summary}
        </pre>
      ) : null}
    </div>
  );
}

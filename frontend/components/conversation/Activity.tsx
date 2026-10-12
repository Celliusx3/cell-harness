"use client";

import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

/** A turn's tool calls and in-between notes behind one line: open while it works, folded after. */
export function Activity({
  live,
  tools,
  children,
}: {
  live: boolean;
  tools: number;
  children: ReactNode;
}) {
  const count = tools > 0 ? ` · ${tools} ${tools === 1 ? "tool" : "tools"}` : "";
  return (
    <details key={live ? "working" : "done"} open={live} className="group">
      <summary className="flex w-fit cursor-pointer list-none items-center gap-1 text-xs text-ink-soft transition hover:text-ink">
        <ChevronRight size={14} className="transition-transform group-open:rotate-90" />
        {live ? "Working…" : "Done"}
        {count}
      </summary>
      <div className="mt-2 ml-[7px] space-y-3 border-l border-line pl-3">{children}</div>
    </details>
  );
}

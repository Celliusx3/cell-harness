"use client";

import { ChevronRight, Ticket } from "lucide-react";
import Link from "next/link";

import { MarkdownBody } from "@/components/conversation/Message";
import type { TicketResultItem } from "@/components/conversation/timelineItems";

/** A ticket's ready result, whole, under a header linking to its worker's chat. */
export function TicketResult({ item }: { item: TicketResultItem }) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-line bg-surface px-3 py-2">
      <Link
        href={`/t/${encodeURIComponent(item.ticketId)}`}
        className="flex items-center gap-2 text-sm text-ink-soft hover:text-ink"
      >
        <Ticket size={14} className="shrink-0" />
        <span className="min-w-0 flex-1 break-words font-medium">{item.title}</span>
        <span className="shrink-0 text-xs">Result</span>
        <ChevronRight size={14} className="shrink-0" />
      </Link>
      <MarkdownBody content={item.text} streaming={false} />
    </div>
  );
}

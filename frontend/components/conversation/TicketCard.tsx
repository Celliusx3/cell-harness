"use client";

import { ChevronRight, Ticket } from "lucide-react";
import Link from "next/link";

import type { ToolItem } from "@/components/conversation/timelineItems";
import { useTicket } from "@/components/conversation/useTicket";
import { TICKET_STATE_LABELS } from "@/lib/tickets";

const ACCEPTED = /^\d+\. accepted ticket ([^,\s]+), titled (.+)$/gm;

interface Accepted {
  id: string;
  title: string;
}

/** A `ticket_route` call: one card for each ticket it accepted. */
export function TicketCards({ item }: { item: ToolItem }) {
  return (
    <div className="space-y-2">
      {acceptedTickets(item).map((ticket) => (
        <TicketCard key={ticket.id} ticket={ticket} />
      ))}
    </div>
  );
}

/** The tickets a `ticket_route` call accepted, from its result's numbered lines. */
export function acceptedTickets(item: ToolItem): Accepted[] {
  if (item.error !== null) return [];
  const text = (item.result ?? []).flatMap((b) => (b.type === "text" ? [b.text] : [])).join("");
  return [...text.matchAll(ACCEPTED)].flatMap(([, id, title]) =>
    id !== undefined && title !== undefined ? [{ id, title }] : [],
  );
}

/** One ticket's title and state, linking to its worker's chat. */
function TicketCard({ ticket }: { ticket: Accepted }) {
  const load = useTicket(ticket.id);
  const title = load.kind === "found" ? load.detail.ticket.title : ticket.title;
  const state = load.kind === "found" ? TICKET_STATE_LABELS[load.detail.ticket.state] : "…";
  return (
    <Link
      href={`/t/${encodeURIComponent(ticket.id)}`}
      className="flex w-full items-center gap-2 rounded-xl border border-line bg-surface-sunken px-3 py-2 text-left text-sm hover:bg-accent-soft"
    >
      <Ticket size={14} className="shrink-0 text-ink-soft" />
      <span className="min-w-0 flex-1 break-words font-medium">{title}</span>
      <span className="shrink-0 text-xs text-ink-soft">{state}</span>
      <ChevronRight size={14} className="shrink-0 text-ink-soft" />
    </Link>
  );
}

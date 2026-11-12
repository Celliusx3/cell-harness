"use client";

import { ChevronRight, Ticket } from "lucide-react";
import Link from "next/link";

import type { ToolItem } from "@/components/conversation/timelineItems";
import { useTicket } from "@/components/conversation/useTicket";
import { TICKET_STATE_LABELS } from "@/lib/tickets";

const STARTED = /^Started ticket ([0-9a-f]+), titled /;

/** A `ticket_accept` call: the ticket's title and state, linking to its worker's chat. */
export function TicketCard({ item }: { item: ToolItem }) {
  const id = ticketIdOf(item);
  const load = useTicket(id);
  const title = load.kind === "found" ? load.detail.ticket.title : titleOf(item.call.arguments);
  const state =
    load.kind === "found" ? TICKET_STATE_LABELS[load.detail.ticket.state] : id ? "…" : "Not started";
  const body = (
    <>
      <Ticket size={14} className="shrink-0 text-ink-soft" />
      <span className="min-w-0 flex-1 break-words font-medium">{title}</span>
      <span className="shrink-0 text-xs text-ink-soft">{state}</span>
      {id !== null && <ChevronRight size={14} className="shrink-0 text-ink-soft" />}
    </>
  );
  const frame =
    "flex w-full items-center gap-2 rounded-xl border border-line bg-surface-sunken px-3 py-2 text-left text-sm";
  if (id === null) return <div className={frame}>{body}</div>;
  return (
    <Link href={`/t/${encodeURIComponent(id)}`} className={`${frame} hover:bg-accent-soft`}>
      {body}
    </Link>
  );
}

function ticketIdOf(item: ToolItem): string | null {
  if (item.error !== null) return null;
  const text = (item.result ?? []).flatMap((b) => (b.type === "text" ? [b.text] : [])).join("");
  return STARTED.exec(text)?.[1] ?? null;
}

function titleOf(raw: string): string {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed === "object" && parsed !== null && "title" in parsed) {
      const title = (parsed as { title: unknown }).title;
      if (typeof title === "string") return title;
    }
  } catch {}
  return "Ticket";
}

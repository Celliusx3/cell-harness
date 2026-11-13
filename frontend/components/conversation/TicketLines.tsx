"use client";

import { useState } from "react";

import { type Accepted, TicketLine } from "@/components/conversation/TicketLine";
import { reportsOf, type TicketReports } from "@/components/conversation/ticketReports";
import type { ToolItem } from "@/components/conversation/timelineItems";
import { useChatTickets } from "@/components/conversation/useChatTickets";
import {
  TraceCollapsible,
  TraceCollapsibleContent,
  TraceCollapsibleTrigger,
  TraceLine,
  TraceTitle,
} from "@/components/ui/trace";
import type { TicketState } from "@/lib/tickets";

const ACCEPTED = /^\d+\. accepted ticket ([^,\s]+), titled (.+)$/gm;

const SETTLED: ReadonlySet<TicketState> = new Set(["done", "dropped", "stopped"]);

interface TicketLinesProps {
  item: ToolItem;
  chatId: string;
  reports: ReadonlyMap<string, TicketReports>;
}

/** A `ticket_route` call's tickets in one box, in the order they started, folded to one line once all are settled. */
export function TicketLines({ item, chatId, reports }: TicketLinesProps) {
  const accepted = acceptedTickets(item);
  const { tickets } = useChatTickets(chatId);
  const [chosen, setChosen] = useState<boolean | null>(null);
  const settled = accepted.every((one) => {
    const state = tickets.find((ticket) => ticket.id === one.id)?.state;
    return state !== undefined && SETTLED.has(state);
  });

  const box = (
    <div className="flex flex-col gap-1.5 rounded-xl border border-line bg-surface-raised px-3 py-2.5">
      {accepted.map((one) => (
        <TicketLine key={one.id} accepted={one} reports={reportsOf(reports, one.id)} />
      ))}
    </div>
  );
  if (!settled) return box;
  return (
    <TraceCollapsible open={chosen ?? false} onOpenChange={setChosen}>
      <TraceCollapsibleTrigger>
        <TraceLine>
          <TraceTitle>{`${accepted.length} ${accepted.length === 1 ? "task" : "tasks"} done`}</TraceTitle>
        </TraceLine>
      </TraceCollapsibleTrigger>
      <TraceCollapsibleContent className="pt-2">{box}</TraceCollapsibleContent>
    </TraceCollapsible>
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

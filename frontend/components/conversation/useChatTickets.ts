"use client";

import { useCallback, useEffect, useState } from "react";

import { useAppEvent } from "@/lib/appEvents";
import { listTickets, type TicketRow, type TicketState } from "@/lib/tickets";

const AT_WORK: ReadonlySet<TicketState> = new Set(["queued", "working", "waiting"]);

export interface ChatTickets {
  tickets: TicketRow[];
  atWork: number;
  needsAnswer: boolean;
}

/** A chat's tickets, how many are at work and whether one waits for an answer, read again on every ticket change. */
export function useChatTickets(chatId: string): ChatTickets {
  const [tickets, setTickets] = useState<TicketRow[]>([]);

  const reload = useCallback(() => {
    listTickets(chatId)
      .then(setTickets)
      .catch(() => setTickets([]));
  }, [chatId]);

  useEffect(reload, [reload]);
  useAppEvent((event) => {
    if (event.type === "tickets/changed" || event.type === "app/connected") reload();
  });

  return {
    tickets,
    atWork: tickets.filter((ticket) => AT_WORK.has(ticket.state)).length,
    needsAnswer: tickets.some((ticket) => ticket.state === "needs_answer"),
  };
}

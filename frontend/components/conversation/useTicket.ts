"use client";

import { useEffect, useState } from "react";

import { getTicket, type TicketDetail } from "@/lib/tickets";

const POLL_MS = 1000;
const WAITING_POLL_MS = 5000;
const BUSY: ReadonlySet<string> = new Set(["working", "queued"]);
const ENDED: ReadonlySet<string> = new Set(["stopped"]);

export type TicketLoad =
  | { kind: "loading" }
  | { kind: "found"; detail: TicketDetail }
  | { kind: "failed"; message: string };

/** One ticket, read every second while its worker runs, every 5 s until it is stopped. */
export function useTicket(id: string | null): TicketLoad {
  const [load, setLoad] = useState<TicketLoad>({ kind: "loading" });

  useEffect(() => {
    if (id === null) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const detail = await getTicket(id);
        if (stopped) return;
        setLoad({ kind: "found", detail });
        const wait = nextPollMs(detail);
        if (wait !== null) timer = setTimeout(poll, wait);
      } catch (error) {
        if (!stopped) setLoad({ kind: "failed", message: messageOf(error) });
      }
    };
    void poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [id]);

  return load;
}

/** How long until the next read: soon while it works, slower otherwise, never once stopped. */
function nextPollMs(detail: TicketDetail): number | null {
  if (detail.running || BUSY.has(detail.ticket.state)) return POLL_MS;
  return ENDED.has(detail.ticket.state) ? null : WAITING_POLL_MS;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Could not load the ticket.";
}

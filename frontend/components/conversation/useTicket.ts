"use client";

import { useEffect, useState } from "react";

import { getTicket, type TicketDetail } from "@/lib/tickets";

const POLL_MS = 1000;

export type TicketLoad =
  | { kind: "loading" }
  | { kind: "found"; detail: TicketDetail }
  | { kind: "failed"; message: string };

/** One ticket, read every second while its worker runs, and once more after it stops. */
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
        if (detail.running || detail.ticket.state === "working") timer = setTimeout(poll, POLL_MS);
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

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Could not load the ticket.";
}

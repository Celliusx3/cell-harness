"use client";

import { useCallback, useEffect, useState } from "react";

import { useAppEvent } from "@/lib/appEvents";
import { listNeedingYou, type TicketRow } from "@/lib/tickets";

export type NeedingYou =
  | { kind: "loading" }
  | { kind: "loaded"; tickets: TicketRow[] }
  | { kind: "failed"; message: string };

/** The tickets that wait for a person, read again whenever any ticket changes. */
export function useNeedingYou(): { needing: NeedingYou; reload: () => void } {
  const [needing, setNeeding] = useState<NeedingYou>({ kind: "loading" });

  const reload = useCallback(() => {
    listNeedingYou()
      .then((tickets) => setNeeding({ kind: "loaded", tickets }))
      .catch((error: unknown) =>
        setNeeding({
          kind: "failed",
          message: error instanceof Error ? error.message : "Could not load the tickets.",
        }),
      );
  }, []);

  useEffect(reload, [reload]);
  useAppEvent((event) => {
    if (event.type === "tickets/changed" || event.type === "app/connected") reload();
  });

  return { needing, reload };
}

/** One chat with tickets that wait for a person, in the order its first one started waiting. */
export interface ChatNeedingYou {
  botId: string;
  tickets: TicketRow[];
}

export function chatsNeedingYou(tickets: TicketRow[]): ChatNeedingYou[] {
  const byBot = new Map<string, TicketRow[]>();
  for (const ticket of tickets) byBot.set(ticket.bot_id, [...(byBot.get(ticket.bot_id) ?? []), ticket]);
  return [...byBot].map(([botId, rows]) => ({ botId, tickets: rows }));
}

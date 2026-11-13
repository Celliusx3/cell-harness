"use client";

import { use } from "react";

import { DrawerButton } from "@/components/chat/Drawer";
import { Timeline } from "@/components/conversation/Timeline";
import { useTicket } from "@/components/conversation/useTicket";
import { useTimeline } from "@/components/conversation/useTimeline";
import { TICKET_STATE_LABELS } from "@/lib/tickets";
import type { SessionEvent } from "@/lib/types";

const NO_EVENTS: SessionEvent[] = [];

/** A ticket's worker chat, to watch only: its steps as they are logged, and no message box. */
export default function TicketPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const load = useTicket(id);
  const detail = load.kind === "found" ? load.detail : null;
  const { items, openTurn, speakers } = useTimeline(detail?.events ?? NO_EVENTS);

  if (load.kind === "failed") {
    return <p className="px-6 py-6 text-sm text-danger">{load.message}</p>;
  }

  return (
    <>
      <header className="flex min-h-14 items-center gap-3 border-b border-line px-4 md:px-6 py-2.5">
        <DrawerButton />
        <div className="flex min-w-0 flex-col">
          <h1 className="truncate text-sm font-semibold leading-tight">
            {detail?.ticket.title ?? ""}
          </h1>
          <span className="text-xs text-ink-soft">
            {detail === null ? "Loading…" : TICKET_STATE_LABELS[detail.ticket.state]}
          </span>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {detail === null ? (
          <p className="px-6 py-6 text-sm text-ink-soft">Loading…</p>
        ) : (
          <Timeline
            items={items}
            openTurn={openTurn}
            speakers={speakers}
            host={null}
            sending={null}
            queued={[]}
            elapsed={null}
            onAnswered={() => {}}
          />
        )}
      </div>
    </>
  );
}

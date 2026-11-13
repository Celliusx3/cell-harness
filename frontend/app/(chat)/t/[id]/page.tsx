"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { use } from "react";

import { DrawerButton } from "@/components/chat/Drawer";
import { isStoppable, StopTicketButton } from "@/components/conversation/StopTicketButton";
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
        {detail !== null && (
          <Link
            href={`/c/${encodeURIComponent(detail.ticket.bot_id)}`}
            className="shrink-0 text-ink-soft hover:text-ink"
            aria-label="Back to chat"
          >
            <ArrowLeft size={16} />
          </Link>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <h1 className="truncate text-sm font-semibold leading-tight">
            {detail?.ticket.title ?? ""}
          </h1>
          <span className="text-xs text-ink-soft">
            {detail === null ? "Loading…" : TICKET_STATE_LABELS[detail.ticket.state]}
          </span>
        </div>
        {detail !== null && isStoppable(detail.ticket.state) && (
          <StopTicketButton ticketId={detail.ticket.id} />
        )}
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
            source={{ kind: "ticket", id }}
          />
        )}
      </div>
    </>
  );
}

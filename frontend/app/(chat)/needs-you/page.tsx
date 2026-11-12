"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useNeedingYou } from "@/components/chat/useNeedingYou";
import { ApiError, listBots } from "@/lib/api";
import { retryTicket, stopTicket, TICKET_STATE_LABELS, type TicketRow } from "@/lib/tickets";

const RETRYABLE: ReadonlySet<string> = new Set(["blocked", "failed"]);

/** Every ticket that waits for a person, across bots, each with stop and, if stuck, retry. */
export default function NeedsYouPage() {
  const { needing, reload } = useNeedingYou();
  const botNames = useBotNames();
  const [error, setError] = useState<string | null>(null);

  const act = async (action: () => Promise<unknown>, failure: string) => {
    try {
      await action();
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : failure);
    }
    reload();
  };

  const shown = error ?? (needing.kind === "failed" ? needing.message : null);

  const stop = (ticket: TicketRow) => {
    if (!window.confirm("Stop this ticket?")) return;
    void act(() => stopTicket(ticket.id), "Could not stop the ticket.");
  };

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">Needs you</h1>
      </header>

      {shown !== null && (
        <div className="border-b border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">
          {shown}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {needing.kind === "loading" && <p className="text-sm text-ink-soft">Loading…</p>}
        {needing.kind === "loaded" && needing.tickets.length === 0 && (
          <p className="text-sm text-ink-soft">Nothing needs you.</p>
        )}
        {needing.kind === "loaded" && needing.tickets.length > 0 && (
          <ul className="max-w-2xl divide-y divide-line rounded-xl border border-line bg-surface-sunken">
            {needing.tickets.map((ticket) => (
              <TicketItem
                key={ticket.id}
                ticket={ticket}
                botName={botNames.get(ticket.bot_id) ?? ticket.bot_id}
                onRetry={() => void act(() => retryTicket(ticket.id), "Could not retry.")}
                onStop={() => stop(ticket)}
              />
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

function useBotNames(): ReadonlyMap<string, string> {
  const [names, setNames] = useState<ReadonlyMap<string, string>>(new Map());
  useEffect(() => {
    listBots()
      .then((bots) => setNames(new Map(bots.map((bot) => [bot.id, bot.name]))))
      .catch(() => setNames(new Map()));
  }, []);
  return names;
}

interface TicketItemProps {
  ticket: TicketRow;
  botName: string;
  onRetry: () => void;
  onStop: () => void;
}

function TicketItem({ ticket, botName, onRetry, onStop }: TicketItemProps) {
  return (
    <li className="flex flex-col gap-2 px-3 py-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Link href={`/t/${encodeURIComponent(ticket.id)}`} className="break-words font-medium hover:underline">
          {ticket.title}
        </Link>
        <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 text-[11px] text-ink-soft">
          {TICKET_STATE_LABELS[ticket.state]}
        </span>
        <span className="text-xs text-ink-soft">{botName}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {RETRYABLE.has(ticket.state) && <RowButton label="Retry" onClick={onRetry} />}
        <RowButton label="Stop" onClick={onStop} />
      </div>
    </li>
  );
}

function RowButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border border-line bg-surface px-3 py-1 text-xs font-medium transition hover:bg-surface-sunken"
    >
      {label}
    </button>
  );
}

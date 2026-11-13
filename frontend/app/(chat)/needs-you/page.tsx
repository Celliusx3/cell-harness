"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DrawerButton } from "@/components/chat/Drawer";
import { chatsNeedingYou, type ChatNeedingYou, useNeedingYou } from "@/components/chat/useNeedingYou";
import { BotAvatar } from "@/components/conversation/BotAvatar";
import { ApiError, listBots } from "@/lib/api";
import {
  retryTicket,
  stopTicket,
  TICKET_STATE_LABELS,
  type TicketRow,
  type TicketState,
} from "@/lib/tickets";

const RETRYABLE: ReadonlySet<string> = new Set(["blocked", "failed"]);

const NEEDS_LABELS: Partial<Record<TicketState, string>> = {
  needs_answer: "asks you something",
  blocked: "is stuck",
  failed: "failed",
};

/** Every chat with work that waits for a person, its tickets under it, each with stop and, if stuck, retry. */
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
      <header className="flex items-center gap-3 border-b border-line px-4 md:px-6 py-3">
        <DrawerButton />
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
          <ul className="max-w-2xl divide-y divide-line rounded-xl border border-line bg-surface-raised">
            {chatsNeedingYou(needing.tickets).map((chat) => (
              <ChatItem
                key={chat.botId}
                chat={chat}
                botName={botNames.get(chat.botId) ?? chat.botId}
                onRetry={(ticket) => void act(() => retryTicket(ticket.id), "Could not retry.")}
                onStop={stop}
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

interface ChatItemProps {
  chat: ChatNeedingYou;
  botName: string;
  onRetry: (ticket: TicketRow) => void;
  onStop: (ticket: TicketRow) => void;
}

function ChatItem({ chat, botName, onRetry, onStop }: ChatItemProps) {
  return (
    <li className="flex flex-col gap-2 px-4 py-3 text-sm">
      <Link
        href={`/c/${encodeURIComponent(chat.botId)}`}
        className="flex items-center gap-2.5 font-semibold hover:text-accent"
      >
        <BotAvatar speaker={{ id: chat.botId, name: botName }} />
        <span className="min-w-0 break-words">{botName}</span>
      </Link>
      <ul className="flex flex-col gap-2 pl-[38px]">
        {chat.tickets.map((ticket) => (
          <li key={ticket.id} className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="min-w-0 break-words">{ticket.title}</span>
            <span className={`text-xs ${ticket.state === "needs_answer" ? "text-attention" : "text-danger"}`}>
              · {NEEDS_LABELS[ticket.state] ?? TICKET_STATE_LABELS[ticket.state]}
            </span>
            <span className="ml-auto flex gap-2">
              {RETRYABLE.has(ticket.state) && <RowButton label="Retry" onClick={() => onRetry(ticket)} />}
              <RowButton label="Stop" onClick={() => onStop(ticket)} />
            </span>
          </li>
        ))}
      </ul>
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

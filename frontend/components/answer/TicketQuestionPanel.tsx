"use client";

import { ArrowUp, MessageCircleQuestionMark } from "lucide-react";
import { useState } from "react";

import type { TicketQuestionItem } from "@/components/conversation/timelineItems";
import { useTicket } from "@/components/conversation/useTicket";
import { ApiError } from "@/lib/api";
import { answerTicket } from "@/lib/tickets";

type Phase = "asking" | "sending" | "sent";

/** A worker's question, unchanged, with a box that answers its ticket while it waits for one. */
export function TicketQuestionPanel({ item }: { item: TicketQuestionItem }) {
  const load = useTicket(item.ticketId);
  const [phase, setPhase] = useState<Phase>("asking");
  const [error, setError] = useState<string | null>(null);
  const waits =
    item.latest && load.kind === "found" && load.detail.ticket.state === "needs_answer";

  const send = async (text: string) => {
    setPhase("sending");
    setError(null);
    try {
      await answerTicket(item.ticketId, text);
      setPhase("sent");
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Could not send the answer.");
      setPhase("asking");
    }
  };

  return (
    <div className="rounded-2xl border border-line bg-surface-raised p-3 shadow-sm">
      <p className="flex items-start gap-2 break-words text-sm font-medium">
        <MessageCircleQuestionMark size={15} className="mt-0.5 shrink-0 text-accent" />
        <span className="min-w-0 flex-1">{item.question}</span>
      </p>
      {waits && phase !== "sent" ? (
        <AnswerBox disabled={phase === "sending"} onSend={(text) => void send(text)} />
      ) : (
        <p className="mt-2 text-xs text-ink-soft">
          {load.kind === "loading" && item.latest ? "…" : "Answered"}
        </p>
      )}
      {error !== null && <p className="mt-2 text-xs text-danger">{error}</p>}
    </div>
  );
}

function AnswerBox({ disabled, onSend }: { disabled: boolean; onSend: (text: string) => void }) {
  const [draft, setDraft] = useState("");
  const submit = () => {
    const text = draft.trim();
    if (text && !disabled) onSend(text);
  };
  return (
    <div className="mt-2 flex items-center gap-2 rounded-xl border border-line bg-surface p-1 pl-3 transition focus-within:border-accent">
      <input
        type="text"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            submit();
          }
        }}
        aria-label="Your answer"
        placeholder="Your answer"
        className="min-w-0 flex-1 bg-transparent py-1.5 text-sm outline-none placeholder:text-ink-soft"
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !draft.trim()}
        aria-label="Send answer"
        title="Send answer"
        className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition hover:opacity-90 disabled:opacity-35"
      >
        <ArrowUp size={16} />
      </button>
    </div>
  );
}

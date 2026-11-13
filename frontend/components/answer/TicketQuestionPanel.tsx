"use client";

import { Check } from "lucide-react";
import { useState } from "react";

import { AnswerList } from "@/components/answer/AnswerList";
import { ApprovalAnswer, LocationAnswer, SecretAnswer } from "@/components/answer/TicketAnswers";
import type { TicketQuestionItem } from "@/components/conversation/timelineItems";
import { useTicket } from "@/components/conversation/useTicket";
import { ApiError } from "@/lib/api";
import { answerTicket, approveTicket, saveTicketSecret } from "@/lib/tickets";
import type { Decision, SessionEvent, ToolCall } from "@/lib/types";

type Phase = { kind: "asking" } | { kind: "sending" } | { kind: "sent"; answer: string };

/** A worker's question in its bot's voice, with the answer its `ask` chooses while its ticket waits. */
export function TicketQuestionPanel({ item }: { item: TicketQuestionItem }) {
  const load = useTicket(item.ticketId);
  const [phase, setPhase] = useState<Phase>({ kind: "asking" });
  const [error, setError] = useState<string | null>(null);
  const waits =
    item.latest && load.kind === "found" && load.detail.ticket.state === "needs_answer";

  const post = async (sent: () => Promise<unknown>, answer: string) => {
    setPhase({ kind: "sending" });
    setError(null);
    try {
      await sent();
      setPhase({ kind: "sent", answer });
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Could not send the answer.");
      setPhase({ kind: "asking" });
    }
  };

  return (
    <div
      className={`space-y-3 border-l-[3px] pl-3 text-sm ${waits && phase.kind !== "sent" ? "border-attention" : "border-line"}`}
    >
      <p className="break-words">{item.question}</p>
      {waits && phase.kind !== "sent" ? (
        <Answer
          item={item}
          call={load.kind === "found" ? waitingCall(load.detail.events, item.approvalCallId) : null}
          disabled={phase.kind === "sending"}
          onSend={(text) =>
            void (item.ask === "secret"
              ? post(() => saveTicketSecret(item.ticketId, text), "Key saved")
              : post(() => answerTicket(item.ticketId, text), text))
          }
          onDecide={(decision) =>
            void post(() => approveTicket(item.ticketId, decision), decisionLabel(decision))
          }
        />
      ) : (
        <Answered phase={phase} loading={load.kind === "loading" && item.latest} />
      )}
      {error !== null && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}

function Answered({ phase, loading }: { phase: Phase; loading: boolean }) {
  if (loading) return <p className="text-xs text-ink-soft">…</p>;
  return (
    <p className="flex items-center gap-1.5 text-sm text-ink-soft">
      <Check size={14} className="shrink-0 text-accent" />
      <span className="min-w-0 break-words">{phase.kind === "sent" ? phase.answer : "Answered"}</span>
    </p>
  );
}

function decisionLabel(decision: Decision): string {
  return decision.kind === "denied" ? "Denied" : "Allowed";
}

function waitingCall(events: SessionEvent[], callId: string | null): ToolCall | null {
  for (const event of events) {
    if (event.type === "tool/call" && event.call.id === callId) return event.call;
  }
  return null;
}

function Answer({
  item,
  call,
  disabled,
  onSend,
  onDecide,
}: {
  item: TicketQuestionItem;
  call: ToolCall | null;
  disabled: boolean;
  onSend: (text: string) => void;
  onDecide: (decision: Decision) => void;
}) {
  switch (item.ask) {
    case "approval":
      return <ApprovalAnswer call={call} disabled={disabled} onDecide={onDecide} />;
    case "secret":
      return <SecretAnswer name={item.secretName} disabled={disabled} onSend={onSend} />;
    case "location":
      return <LocationAnswer disabled={disabled} onSend={onSend} />;
    case "choice":
    case "text":
      return <AnswerList options={item.options} disabled={disabled} autoFocus={false} onAnswer={onSend} />;
  }
}

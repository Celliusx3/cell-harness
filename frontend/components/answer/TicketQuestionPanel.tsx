"use client";

import { useState } from "react";

import { AnswerList } from "@/components/answer/AnswerList";
import {
  ApprovalAnswer,
  LocationAnswer,
  SecretAnswer,
  TakeoverAnswer,
} from "@/components/answer/TicketAnswers";
import type { TicketQuestionItem } from "@/components/conversation/timelineItems";
import { useTicket } from "@/components/conversation/useTicket";
import { ApiError } from "@/lib/api";
import { answerTicket, approveTicket, saveTicketSecret } from "@/lib/tickets";
import type { Decision, SessionEvent, ToolCall } from "@/lib/types";

type Phase = "asking" | "sending" | "sent";

/** A worker's question in its bot's voice while its ticket waits; once answered it lives under the ticket's line. */
export function TicketQuestionPanel({ item }: { item: TicketQuestionItem }) {
  const load = useTicket(item.ticketId);
  const [phase, setPhase] = useState<Phase>("asking");
  const [error, setError] = useState<string | null>(null);
  const waits =
    item.latest && load.kind === "found" && load.detail.ticket.state === "needs_answer";

  const post = async (sent: () => Promise<unknown>) => {
    setPhase("sending");
    setError(null);
    try {
      await sent();
      setPhase("sent");
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Could not send the answer.");
      setPhase("asking");
    }
  };

  if (!waits || phase === "sent") return null;
  return (
    <div className="space-y-3 border-l-[3px] border-attention pl-3 text-sm">
      <p className="break-words">{item.question}</p>
      <Answer
        item={item}
        call={load.kind === "found" ? waitingCall(load.detail.events, item.approvalCallId) : null}
        disabled={phase === "sending"}
        onSend={(text) =>
          void post(() =>
            item.ask === "secret"
              ? saveTicketSecret(item.ticketId, text)
              : answerTicket(item.ticketId, text),
          )
        }
        onDecide={(decision) => void post(() => approveTicket(item.ticketId, decision))}
      />
      {error !== null && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
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
    case "takeover":
      return <TakeoverAnswer disabled={disabled} onSend={onSend} />;
    case "choice":
    case "text":
      return <AnswerList options={item.options} disabled={disabled} autoFocus={false} onAnswer={onSend} />;
  }
}

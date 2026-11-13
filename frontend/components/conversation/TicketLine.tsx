"use client";

import { isStoppable } from "@/components/conversation/StopTicketButton";
import { TicketFold } from "@/components/conversation/TicketFold";
import type { TicketReports } from "@/components/conversation/ticketReports";
import { ticketWork, type TicketWork } from "@/components/conversation/ticketWork";
import { elapsedLabel } from "@/components/conversation/useElapsed";
import { useTicket } from "@/components/conversation/useTicket";
import {
  TraceCollapsible,
  TraceCollapsibleContent,
  TraceCollapsibleTrigger,
  TraceDescription,
  TraceLine,
  TraceTitle,
} from "@/components/ui/trace";
import type { TicketRow, TicketState } from "@/lib/tickets";

const AT_WORK: ReadonlySet<TicketState> = new Set(["queued", "working", "waiting"]);

export interface Accepted {
  id: string;
  title: string;
}

/** One ticket as its bot's thinking: what its worker does now, opening to its result, questions and steps. */
export function TicketLine({ accepted, reports }: { accepted: Accepted; reports: TicketReports }) {
  const load = useTicket(accepted.id);
  if (load.kind !== "found") {
    return <Line title={accepted.title} status="pending" detail={load.kind === "failed" ? load.message : "starting"} />;
  }
  const { ticket, events, running } = load.detail;
  const work = ticketWork(events);
  return (
    <TraceCollapsible>
      <TraceCollapsibleTrigger>
        <TicketSummary ticket={ticket} work={work} atWork={running || AT_WORK.has(ticket.state)} />
      </TraceCollapsibleTrigger>
      <TraceCollapsibleContent className="border-line pl-3">
        <TicketFold ticketId={ticket.id} reports={reports} work={work} stoppable={isStoppable(ticket.state)} />
      </TraceCollapsibleContent>
    </TraceCollapsible>
  );
}

function TicketSummary({ ticket, work, atWork }: { ticket: TicketRow; work: TicketWork; atWork: boolean }) {
  if (ticket.state === "needs_answer") {
    return <Line title={ticket.title} status="waiting" detail="needs your answer below" />;
  }
  if (atWork) {
    const elapsed = elapsedLabel(Date.now() - Date.parse(ticket.created_at));
    return <Line title={ticket.title} status="running" detail={work.now} elapsed={elapsed} />;
  }
  return <Line title={ticket.title} status={endedStatus(ticket.state)} detail={endedDetail(ticket.state, work.steps.length)} />;
}

type LineStatus = "running" | "waiting" | "pending" | "error" | "done";

function Line({
  title,
  status,
  detail,
  elapsed,
}: {
  title: string;
  status: LineStatus;
  detail: string;
  elapsed?: string;
}) {
  return (
    <TraceLine status={status === "running" || status === "pending" || status === "error" ? status : undefined}>
      <Dot status={status} />
      <TraceTitle className="font-medium text-ink">{title}</TraceTitle>
      <TraceDescription className={status === "waiting" ? "text-attention" : undefined}>
        · {detail}
      </TraceDescription>
      {elapsed !== undefined && <TraceDescription className="font-mono text-xs">{elapsed}</TraceDescription>}
    </TraceLine>
  );
}

const DOT: Record<LineStatus, string> = {
  running: "bg-accent animate-pulse motion-reduce:animate-none",
  waiting: "bg-attention",
  pending: "bg-line",
  error: "bg-danger",
  done: "bg-ink-soft/50",
};

function Dot({ status }: { status: LineStatus }) {
  return <span aria-hidden className={`size-1.5 shrink-0 rounded-full ${DOT[status]}`} />;
}

function endedStatus(state: TicketState): LineStatus {
  return state === "failed" || state === "blocked" ? "error" : "done";
}

function endedDetail(state: TicketState, steps: number): string {
  const count = `${steps} ${steps === 1 ? "step" : "steps"}`;
  switch (state) {
    case "failed":
      return `failed after ${count}`;
    case "blocked":
      return `blocked after ${count}`;
    case "dropped":
    case "stopped":
      return `stopped after ${count}`;
    default:
      return count;
  }
}

import { request } from "./api";
import type { SessionEvent } from "./types";

/** How far a ticket has got, as its worker last reported. */
export type TicketState =
  | "working"
  | "waiting"
  | "needs_answer"
  | "blocked"
  | "failed"
  | "done"
  | "dropped";

/** One row of `GET /api/tickets`, its time ISO UTC. */
export interface TicketRow {
  id: string;
  bot_id: string;
  title: string;
  state: TicketState;
  created_at: string;
}

/** `GET /api/tickets/{id}`: the ticket, its worker's log, and whether the worker is in flight. */
export interface TicketDetail {
  ticket: TicketRow;
  events: SessionEvent[];
  running: boolean;
}

export const TICKET_STATE_LABELS: Record<TicketState, string> = {
  working: "Working",
  waiting: "Waiting",
  needs_answer: "Needs you",
  blocked: "Blocked",
  failed: "Failed",
  done: "Done",
  dropped: "Dropped",
};

export const getTicket = (id: string) =>
  request<TicketDetail>(`/tickets/${encodeURIComponent(id)}`);

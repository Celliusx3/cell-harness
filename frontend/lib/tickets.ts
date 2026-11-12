import { request } from "./api";
import type { Decision, SessionEvent } from "./types";

/** How the person answers a worker's question: typed, an option tapped, a key pasted, or a location shared. */
export type TicketAsk = "text" | "choice" | "secret" | "location" | "approval";

/** A ticket's worker ending, as its bot hears it; `approval` asks are built by the host. */
export interface TicketReport {
  ticket_id: string;
  title: string;
  state: "progress" | "waiting" | "ready" | "blocked" | "failed" | "dropped";
  text: string;
  question: string | null;
  ask: TicketAsk;
  options: string[] | null;
  secret_name: string | null;
  approval_call_id: string | null;
  approval_tool: string | null;
}

/** How far a ticket has got, as its worker last reported. */
export type TicketState =
  | "queued"
  | "working"
  | "waiting"
  | "needs_answer"
  | "blocked"
  | "failed"
  | "done"
  | "dropped"
  | "stopped";

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
  queued: "Queued",
  working: "Working",
  waiting: "Waiting",
  needs_answer: "Needs you",
  blocked: "Blocked",
  failed: "Failed",
  done: "Done",
  dropped: "Dropped",
  stopped: "Stopped",
};

export const getTicket = (id: string) =>
  request<TicketDetail>(`/tickets/${encodeURIComponent(id)}`);

/** The person's answer to the ticket's question; refused unless the ticket needs one. */
export const answerTicket = (id: string, text: string) =>
  request<TicketRow>(`/tickets/${encodeURIComponent(id)}/answer`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });

/** The key the ticket's question asks for, saved for its bot; only its name reaches the worker. */
export const saveTicketSecret = (id: string, value: string) =>
  request<TicketRow>(`/tickets/${encodeURIComponent(id)}/secret`, {
    method: "POST",
    body: JSON.stringify({ value }),
  });

/** The person's decision on the call the ticket's worker waits to have allowed. */
export const approveTicket = (id: string, decision: Decision) =>
  request<TicketRow>(`/tickets/${encodeURIComponent(id)}/approve`, {
    method: "POST",
    body: JSON.stringify({ decision }),
  });

const ticketPath = (id: string, action: string) => `/tickets/${encodeURIComponent(id)}${action}`;

/** Every bot's tickets that wait for a person: a question, a block or a failure, oldest first. */
export const listNeedingYou = () => request<TicketRow[]>("/tickets/needs-you");

export const stopTicket = (id: string) => request<void>(ticketPath(id, "/stop"), { method: "POST" });

/** Run a blocked or failed ticket's worker again, in the same chat and folder. */
export const retryTicket = (id: string) =>
  request<TicketRow>(ticketPath(id, "/retry"), { method: "POST" });

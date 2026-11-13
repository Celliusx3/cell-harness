/** What a ticket's worker has done and is doing now, read from its log. */

import { humanise } from "@/lib/toolName";
import type { SessionEvent, ToolCall } from "@/lib/types";

const BOOKKEEPING: ReadonlySet<string> = new Set(["ticket_report", "ticket_note"]);

export interface TicketWork {
  /** Each tool call the worker made, as a person reads it. */
  steps: string[];
  /** The worker's current step: the tool it runs, or whether it is thinking or writing. */
  now: string;
}

export function ticketWork(events: SessionEvent[]): TicketWork {
  const calls = events.flatMap((event) =>
    event.type === "tool/call" && !BOOKKEEPING.has(event.call.name) ? [event.call] : [],
  );
  const answered = new Set(
    events.flatMap((event) => (event.type === "tool/result" ? [event.message.tool_call_id] : [])),
  );
  const running = calls.filter((call) => !answered.has(call.id)).at(-1);
  const now = running === undefined ? idleStep(events) : lowerFirst(stepLabel(running));
  return { steps: calls.map(stepLabel), now };
}

/** A call's own `description` when it gives one, else the tool's name in words. */
function stepLabel(call: ToolCall): string {
  const described = descriptionOf(call.arguments);
  return described ?? sentenceCase(humanise(call.name).label);
}

function idleStep(events: SessionEvent[]): string {
  const last = events.at(-1);
  const writing = last?.type === "assistant/chunk" && last.chunk.kind === "text";
  return writing ? "writing" : "thinking";
}

function descriptionOf(raw: string): string | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (parsed === null || typeof parsed !== "object" || !("description" in parsed)) return null;
  const { description } = parsed;
  return typeof description === "string" && description.trim() !== "" ? description.trim() : null;
}

function sentenceCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function lowerFirst(text: string): string {
  return text.charAt(0).toLowerCase() + text.slice(1);
}

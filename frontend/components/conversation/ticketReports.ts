/** What each ticket's worker reported to the bot: its result, and the questions it asked the person. */

import type { TimelineItem } from "@/components/conversation/timelineItems";

export interface TicketReports {
  result: string | null;
  questions: string[];
}

const NONE: TicketReports = { result: null, questions: [] };

export function ticketReports(items: TimelineItem[]): ReadonlyMap<string, TicketReports> {
  return items.reduce((reports, item) => {
    if (item.kind !== "ticketResult" && item.kind !== "ticketQuestion") return reports;
    const held = reports.get(item.ticketId) ?? NONE;
    const next =
      item.kind === "ticketResult"
        ? { ...held, result: item.text }
        : { ...held, questions: [...held.questions, item.question] };
    return new Map(reports).set(item.ticketId, next);
  }, new Map<string, TicketReports>());
}

export function reportsOf(reports: ReadonlyMap<string, TicketReports>, ticketId: string): TicketReports {
  return reports.get(ticketId) ?? NONE;
}

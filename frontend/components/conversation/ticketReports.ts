/** The questions each ticket's worker asked the person, from its reports. */

import type { TimelineItem } from "@/components/conversation/timelineItems";

export interface TicketReports {
  questions: string[];
}

const NONE: TicketReports = { questions: [] };

export function ticketReports(items: TimelineItem[]): ReadonlyMap<string, TicketReports> {
  return items.reduce((reports, item) => {
    if (item.kind !== "ticketQuestion") return reports;
    const held = reports.get(item.ticketId) ?? NONE;
    return new Map(reports).set(item.ticketId, { questions: [...held.questions, item.question] });
  }, new Map<string, TicketReports>());
}

export function reportsOf(reports: ReadonlyMap<string, TicketReports>, ticketId: string): TicketReports {
  return reports.get(ticketId) ?? NONE;
}

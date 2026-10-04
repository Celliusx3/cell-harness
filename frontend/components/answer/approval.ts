/** A gated call read from the timeline: which one waits on the person, and how it is named */

import { CLIENT_TOOLS } from "@/components/answer/clientTools";
import type { TimelineItem, ToolItem } from "@/components/conversation/timelineItems";
import { humanise } from "@/lib/toolName";

/** The first unanswered call that is not a client tool, once no turn is open. */
export function waitingApproval(
  items: TimelineItem[],
  openTurn: number | null,
): ToolItem | null {
  if (openTurn !== null) return null;
  return (
    items.find(
      (item): item is ToolItem =>
        item.kind === "tool" &&
        item.result === null &&
        CLIENT_TOOLS[item.call.name] === undefined,
    ) ?? null
  );
}

/** The call's label, then its server when it has one: "edit note · memory". */
export function approvalTitle(item: ToolItem): string {
  const { server, label } = humanise(item.call.name);
  return server === null ? label : `${label} · ${server}`;
}

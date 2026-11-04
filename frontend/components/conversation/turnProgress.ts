/** Where the open turn stands: starting, thinking between steps, running a tool, or writing its reply. */

import type { TimelineItem, ToolItem } from "@/components/conversation/timelineItems";
import type { Row } from "@/components/conversation/turnRows";
import { humanise } from "@/lib/toolName";

export type Progress =
  | { kind: "starting" }
  | { kind: "thinking" }
  | { kind: "running"; tool: string }
  | { kind: "writing" };

export function progressOf(
  rows: Row[],
  items: TimelineItem[],
  openTurn: number | null,
  sending: string | null,
): Progress | null {
  if (sending === null && openTurn === null) return null;
  const answered = rows.some((row) => row.kind === "answer" && row.turn === openTurn);
  if (!answered) return { kind: "starting" };
  return stepOf(items.filter((item) => item.kind !== "instructions" && item.turn === openTurn));
}

function stepOf(turn: TimelineItem[]): Progress {
  const running = turn.filter((item): item is ToolItem => item.kind === "tool" && item.result === null);
  const newestCall = running.at(-1);
  if (newestCall !== undefined) return { kind: "running", tool: humanise(newestCall.call.name).label };
  const newest = turn.at(-1);
  const isWriting = newest?.kind === "assistant" && newest.content.trim() !== "";
  return isWriting ? { kind: "writing" } : { kind: "thinking" };
}

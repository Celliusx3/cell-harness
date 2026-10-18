/** A chat's items as rows: each turn's work folded behind one line, its reply and asks left out. */

import type { Speaker, TimelineItem, ToolItem } from "@/components/conversation/timelineItems";

const NO_RESPONSE = "NO_RESPONSE";

export type Part =
  | { kind: "item"; item: TimelineItem }
  | { kind: "activity"; key: string; turn: number; items: TimelineItem[] };

/** A turn's answer is one block under the bot that gave it, which is null in a bot's own chat. */
export type Row =
  | { kind: "item"; item: TimelineItem }
  | { kind: "answer"; key: string; speaker: Speaker | null; parts: Part[] };

export interface TurnShape {
  /** In a group's chat, the bot that spoke each turn. */
  speakers: ReadonlyMap<number, Speaker>;
  /** Whether a tool's card stays in view. */
  stays: (item: ToolItem) => boolean;
}

export function turnRows(items: TimelineItem[], shape: TurnShape): Row[] {
  const rows: Row[] = [];
  let run: { turn: number; items: TimelineItem[] } | null = null;
  for (const item of items) {
    const turn = turnOf(item);
    if (run !== null && run.turn !== turn) {
      rows.push(...oneTurn(run.items, run.turn, shape));
      run = null;
    }
    if (turn === null) rows.push({ kind: "item", item });
    else if (run === null) run = { turn, items: [item] };
    else run.items.push(item);
  }
  if (run !== null) rows.push(...oneTurn(run.items, run.turn, shape));
  return rows;
}

function turnOf(item: TimelineItem): number | null {
  return item.kind === "instructions" ? null : item.turn;
}

function oneTurn(items: TimelineItem[], turn: number, shape: TurnShape): Row[] {
  const speaker = shape.speakers.get(turn) ?? null;
  const shown = items.filter((item) => isShown(item, speaker !== null));
  const asked: Row[] = shown
    .filter((item) => item.kind === "user")
    .map((item) => ({ kind: "item", item }));
  const answer = shown.filter((item) => item.kind !== "user");
  const first = answer[0];
  if (first === undefined) return asked;
  const said = [...items].reverse().find((item) => item.kind === "assistant" && item.content.trim());
  const reply = said !== undefined && shown.includes(said) ? said : undefined;
  return [
    ...asked,
    {
      kind: "answer",
      key: `r${first.key}`,
      speaker,
      parts: partsOf(answer, turn, reply, shape.stays),
    },
  ];
}

function partsOf(
  answer: TimelineItem[],
  turn: number,
  reply: TimelineItem | undefined,
  stays: TurnShape["stays"],
): Part[] {
  const parts: Part[] = [];
  const folded: TimelineItem[] = [];
  let foldAt = -1;
  for (const item of answer) {
    if (isKept(item, reply, stays)) {
      parts.push({ kind: "item", item });
    } else {
      if (foldAt < 0) foldAt = parts.length;
      folded.push(item);
    }
  }
  const first = folded[0];
  if (first !== undefined) {
    parts.splice(foldAt, 0, { kind: "activity", key: `w${first.key}`, turn, items: folded });
  }
  return parts;
}

/** Whether anything of `item` reaches the screen. */
function isShown(item: TimelineItem, inGroup: boolean): boolean {
  if (item.kind !== "assistant") return true;
  const text = item.content.trim();
  if (!text) return false;
  return !inGroup || !couldBeNoResponse(text, item.streaming);
}

function couldBeNoResponse(text: string, streaming: boolean): boolean {
  return streaming ? NO_RESPONSE.startsWith(text) : text === NO_RESPONSE;
}

function isKept(
  item: TimelineItem,
  reply: TimelineItem | undefined,
  stays: (item: ToolItem) => boolean,
): boolean {
  switch (item.kind) {
    case "user":
      return true;
    case "assistant":
      return item === reply;
    case "tool":
      return stays(item);
    case "notice":
      return item.tone !== "note";
    case "compaction":
    case "instructions":
      return true;
  }
}

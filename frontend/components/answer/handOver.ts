/** A `hand_over` call read from the timeline: the step asked of the person, how they answered, and which call still waits */

import { z } from "zod";

import type { TimelineItem, ToolItem } from "@/components/conversation/timelineItems";
import type { ContentBlock, HandOver, HandOverAnswer } from "@/lib/types";

export const HAND_OVER = "hand_over";

const HandOverArguments: z.ZodType<HandOver> = z.object({ step: z.string().min(1) });
const HandOverAnswerResult: z.ZodType<HandOverAnswer> = z.strictObject({ finished: z.boolean() });

/** The call's arguments, or null when they do not parse as a hand-over. */
export function handOverOf(item: ToolItem): HandOver | null {
  return parsedJson(HandOverArguments, item.call.arguments);
}

/** The answer read from the call's result, or null when it does not parse as one. */
export function handOverAnswerOf(result: ContentBlock[]): HandOverAnswer | null {
  const text = result.find(
    (b): b is Extract<ContentBlock, { type: "text" }> => b.type === "text",
  );
  return text === undefined ? null : parsedJson(HandOverAnswerResult, text.text);
}

/** The last unanswered `hand_over` call, once no turn is open. */
export function waitingHandOver(
  items: TimelineItem[],
  openTurn: number | null,
): ToolItem | null {
  if (openTurn !== null) return null;
  return (
    items
      .filter(
        (item): item is ToolItem =>
          item.kind === "tool" && item.call.name === HAND_OVER && item.result === null,
      )
      .at(-1) ?? null
  );
}

function parsedJson<T>(schema: z.ZodType<T>, raw: string): T | null {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  const parsed = schema.safeParse(value);
  return parsed.success ? parsed.data : null;
}

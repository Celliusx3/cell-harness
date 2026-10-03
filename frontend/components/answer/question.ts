/** An `ask_user` call read from the timeline: what was asked, what was chosen, and which call still waits */

import type { TimelineItem, ToolItem } from "@/components/conversation/timelineItems";
import type { Answer, ContentBlock } from "@/lib/types";

export const ASK_USER = "ask_user";

export interface Question {
  question: string;
  options: string[];
}

/** The call's arguments as a question, or null when they do not parse as one. */
export function questionOf(item: ToolItem): Question | null {
  return parsed(item.call.arguments, isQuestionArguments);
}

/** The option or text the answer carried, read from the call's result. */
export function chosenLabel(result: ContentBlock[]): string | null {
  const text = result.find(
    (b): b is Extract<ContentBlock, { type: "text" }> => b.type === "text",
  );
  return text === undefined ? null : (parsed(text.text, isAnswer)?.choice ?? null);
}

/** The last unanswered `ask_user` call, once no turn is open. */
export function waitingQuestion(
  items: TimelineItem[],
  openTurn: number | null,
): ToolItem | null {
  if (openTurn !== null) return null;
  return (
    items
      .filter(
        (item): item is ToolItem =>
          item.kind === "tool" && item.call.name === ASK_USER && item.result === null,
      )
      .at(-1) ?? null
  );
}

function parsed<T>(raw: string, fits: (value: unknown) => value is T): T | null {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  return fits(value) ? value : null;
}

function isQuestionArguments(value: unknown): value is Question {
  return (
    typeof value === "object" &&
    value !== null &&
    "question" in value &&
    typeof value.question === "string" &&
    "options" in value &&
    Array.isArray(value.options) &&
    value.options.every((option: unknown) => typeof option === "string")
  );
}

function isAnswer(value: unknown): value is Answer {
  return (
    typeof value === "object" &&
    value !== null &&
    "choice" in value &&
    typeof value.choice === "string"
  );
}

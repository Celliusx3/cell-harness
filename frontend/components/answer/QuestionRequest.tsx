"use client";

import { MessageCircleQuestionMark } from "lucide-react";

import type { ClientToolProps } from "@/components/answer/useClientTool";
import { useClientTool } from "@/components/answer/useClientTool";
import type { ToolItem } from "@/components/conversation/timelineItems";
import type { Answer, ContentBlock } from "@/lib/types";

interface QuestionArguments {
  question: string;
  options: string[];
}

const OPTION =
  "w-full break-words rounded-lg border border-line bg-surface px-3 py-2 text-left text-sm font-medium transition hover:bg-surface-sunken";

/** The card for an `ask_user` call: the question, one button per option, then what became of it. */
export function QuestionRequest(props: ClientToolProps) {
  const { item } = props;
  const { pending, phase, send } = useClientTool<Answer>(props);
  const asked = parsed(item.call.arguments, isQuestionArguments);

  return (
    <div className="rounded-xl border border-accent/40 bg-accent-soft px-3 py-2.5 text-sm">
      <div className="flex items-start gap-2">
        <MessageCircleQuestionMark size={14} className="mt-0.5 shrink-0 text-accent" />
        <span className="min-w-0 break-words font-medium">
          {asked?.question ?? "This question could not be shown."}
        </span>
      </div>
      {asked !== null &&
        (pending && phase === "asking" ? (
          <div className="mt-2 flex flex-col gap-2">
            {asked.options.map((label) => (
              <button
                key={label}
                type="button"
                onClick={() => void send({ kind: "shared", data: { choice: label } })}
                className={OPTION}
              >
                {label}
              </button>
            ))}
          </div>
        ) : (
          <p className="mt-2 break-words text-xs text-ink-soft">{outcome(item)}</p>
        ))}
    </div>
  );
}

function outcome({ result, error }: ToolItem): string {
  if (result === null) return "Sent. Waiting for the assistant…";
  switch (error) {
    case null: {
      const choice = chosenLabel(result);
      return choice === null ? "Answered." : `Answered: ${choice}`;
    }
    case "SKIPPED":
      return "Skipped. You answered in your own words.";
    case "INVALID_ARGUMENTS":
      return "Not asked. The question did not fit.";
    default:
      return "Question cancelled.";
  }
}

function chosenLabel(result: ContentBlock[]): string | null {
  const text = result.find(
    (b): b is Extract<ContentBlock, { type: "text" }> => b.type === "text",
  );
  return text === undefined ? null : (parsed(text.text, isAnswer)?.choice ?? null);
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

function isQuestionArguments(value: unknown): value is QuestionArguments {
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

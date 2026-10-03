"use client";

import { MessageCircleQuestionMark } from "lucide-react";

import { chosenLabel, questionOf } from "@/components/answer/question";
import type { ClientToolProps } from "@/components/answer/useClientTool";
import type { ToolItem } from "@/components/conversation/timelineItems";

/** The conversation's one-line record of an `ask_user` call: the question and what became of it. */
export function QuestionRequest({ item }: ClientToolProps) {
  const answered = item.result !== null && item.error === null;

  return (
    <div
      className={`flex items-start gap-2 text-xs ${answered ? "text-ink" : "text-ink-soft"}`}
    >
      <MessageCircleQuestionMark size={14} className="mt-px shrink-0 text-accent" />
      <span className="min-w-0 break-words">{record(item)}</span>
    </div>
  );
}

function record(item: ToolItem): string {
  const question = questionOf(item)?.question ?? "A question";
  const { result, error } = item;
  if (result === null) return `${question} · waiting for your answer`;
  switch (error) {
    case null:
      return `${question} → ${chosenLabel(result) ?? "answered"}`;
    case "SKIPPED":
      return `${question} → skipped`;
    case "INVALID_ARGUMENTS":
      return "Not asked. The question did not fit.";
    default:
      return `${question} → cancelled`;
  }
}

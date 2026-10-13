"use client";

import { Hand } from "lucide-react";

import { handOverAnswerOf, handOverOf } from "@/components/answer/handOver";
import type { ClientToolProps } from "@/components/answer/useClientTool";
import type { ToolItem } from "@/components/conversation/timelineItems";
import type { ContentBlock } from "@/lib/types";

/** The conversation's one-line record of a `hand_over` call: the step asked and what became of it. */
export function HandOverRequest({ item }: ClientToolProps) {
  const answered = item.result !== null && item.error === null;

  return (
    <div
      className={`flex items-start gap-2 text-xs ${answered ? "text-ink" : "text-ink-soft"}`}
    >
      <Hand size={14} className="mt-px shrink-0 text-accent" />
      <span className="min-w-0 break-words">{record(item)}</span>
    </div>
  );
}

function record(item: ToolItem): string {
  const step = handOverOf(item)?.step;
  const label = step === undefined ? "Needs you" : `Needs you: ${step}`;
  const { result, error } = item;
  if (result === null) return `${label} · waiting for you`;
  switch (error) {
    case null:
      return `${label} → ${answerLabel(result)}`;
    case "SKIPPED":
      return `${label} → skipped`;
    case "INVALID_ARGUMENTS":
      return "Not handed over. The request did not fit.";
    default:
      return `${label} → cancelled`;
  }
}

function answerLabel(result: ContentBlock[]): string {
  const handOverAnswer = handOverAnswerOf(result);
  if (handOverAnswer === null) return "the answer could not be read";
  return handOverAnswer.finished ? "done" : "skipped";
}

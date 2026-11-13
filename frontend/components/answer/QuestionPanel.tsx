"use client";

import { MessageCircleQuestionMark } from "lucide-react";
import type { KeyboardEvent } from "react";

import { AnswerList } from "@/components/answer/AnswerList";
import { FADE_ABOVE } from "@/components/answer/answerStyles";
import { questionOf } from "@/components/answer/question";
import { useClientTool } from "@/components/answer/useClientTool";
import type { ToolItem } from "@/components/conversation/timelineItems";
import type { Answer } from "@/lib/types";

/** A waiting question answered from one list of options and the person's own words; skipped only when `onSkip` is given. */
export function QuestionPanel({
  item,
  conversationId,
  onAnswered,
  onSkip,
}: {
  item: ToolItem;
  conversationId: string;
  onAnswered: () => void;
  onSkip?: () => void;
}) {
  const { phase, send } = useClientTool<Answer>({ item, conversationId, onAnswered });
  const asked = questionOf(item);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (phase !== "asking" || onSkip === undefined) return;
    if (event.key !== "Escape" || event.nativeEvent.isComposing) return;
    event.preventDefault();
    onSkip();
  };

  return (
    <div className={`relative bg-surface px-4 pb-5 pt-2 ${FADE_ABOVE}`}>
      <div
        onKeyDown={handleKeyDown}
        className="mx-auto max-w-3xl rounded-2xl border border-attention/50 bg-surface-raised p-3 shadow-sm"
      >
        <p className="mb-3 break-words text-sm font-medium">
          {asked?.question ?? "This question could not be shown."}
        </p>
        {phase === "asking" ? (
          <>
            <AnswerList
              options={asked?.options ?? []}
              disabled={false}
              autoFocus
              onAnswer={(choice) => void send({ kind: "shared", data: { choice } })}
            />
            {onSkip !== undefined && (
              <div className="mt-2 flex items-center gap-1.5 text-xs text-ink-soft">
                <button type="button" onClick={onSkip} className="transition hover:text-ink">
                  Skip
                </button>
                <kbd className="rounded border border-line px-1 font-sans">Esc</kbd>
              </div>
            )}
          </>
        ) : (
          <p className="text-xs text-ink-soft">Sent. Waiting for the assistant…</p>
        )}
      </div>
    </div>
  );
}

/** The skipped question, folded to a line above the message box. */
export function QuestionBar({
  question,
  onAnswer,
}: {
  question: string;
  onAnswer: () => void;
}) {
  return (
    <div className={`relative z-10 bg-surface px-4 pt-2 ${FADE_ABOVE}`}>
      <div className="mx-auto flex max-w-3xl items-center gap-2 rounded-xl border border-attention/50 bg-surface-raised px-3 py-1.5 text-sm">
        <MessageCircleQuestionMark size={14} className="shrink-0 text-attention" />
        <span className="min-w-0 flex-1 break-words">{question}</span>
        <button
          type="button"
          onClick={onAnswer}
          className="shrink-0 rounded-lg bg-action px-3 py-1 text-xs font-medium text-on-action transition hover:opacity-90"
        >
          Answer
        </button>
      </div>
    </div>
  );
}

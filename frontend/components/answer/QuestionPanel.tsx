"use client";

import { ArrowUp, MessageCircleQuestionMark } from "lucide-react";
import type { KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { questionOf } from "@/components/answer/question";
import { useClientTool } from "@/components/answer/useClientTool";
import type { ToolItem } from "@/components/conversation/timelineItems";
import type { Answer } from "@/lib/types";

const FADE_ABOVE =
  "before:pointer-events-none before:absolute before:inset-x-0 before:bottom-full before:h-8 before:bg-gradient-to-t before:from-surface before:to-transparent before:content-['']";

const OPTION =
  "flex w-full items-start gap-2.5 rounded-lg border border-line bg-surface px-3 py-2 text-left text-sm font-medium transition hover:bg-surface-sunken";

const BADGE =
  "flex size-5 shrink-0 items-center justify-center rounded-md border border-line bg-surface-sunken text-xs text-ink-soft";

const OPTION_KEY = /^[1-9]$/;

/** A waiting question answered by an option, its number key or typed text; skipped only when `onSkip` is given. */
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
  const [draft, setDraft] = useState("");
  const panel = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const asked = questionOf(item);

  useEffect(() => {
    panel.current?.focus();
  }, []);

  const answer = (choice: string) => void send({ kind: "shared", data: { choice } });

  const submit = () => {
    const text = draft.trim();
    if (text) answer(text);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (phase !== "asking") return;
    if (event.key === "Escape" && onSkip !== undefined && !event.nativeEvent.isComposing) {
      event.preventDefault();
      onSkip();
      return;
    }
    if (event.target === input.current || asked === null) return;
    if (event.metaKey || event.ctrlKey || event.altKey || !OPTION_KEY.test(event.key)) return;
    const option = asked.options[Number(event.key) - 1];
    if (option === undefined) return;
    event.preventDefault();
    answer(option);
  };

  return (
    <div className={`relative bg-surface px-4 pb-5 pt-2 ${FADE_ABOVE}`}>
      <div
        ref={panel}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="mx-auto max-w-3xl rounded-2xl border border-line bg-surface-raised p-3 shadow-sm outline-none"
      >
        <p className="break-words text-sm font-medium">
          {asked?.question ?? "This question could not be shown."}
        </p>
        {phase === "asking" ? (
          <>
            {asked !== null && (
              <div className="mt-3 flex flex-col gap-2">
                {asked.options.map((label, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => answer(label)}
                    className={OPTION}
                  >
                    <span className={BADGE}>{index + 1}</span>{" "}
                    <span className="min-w-0 break-words">{label}</span>
                  </button>
                ))}
              </div>
            )}
            <div className="mt-2 flex items-center gap-2 rounded-xl border border-line bg-surface p-1 pl-3 transition focus-within:border-accent">
              <input
                ref={input}
                type="text"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    submit();
                  }
                }}
                aria-label="Type your own answer"
                placeholder="Type your own answer"
                className="min-w-0 flex-1 bg-transparent py-1.5 text-sm outline-none placeholder:text-ink-soft"
              />
              <button
                type="button"
                onClick={submit}
                disabled={!draft.trim()}
                aria-label="Send answer"
                className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition hover:opacity-90 disabled:opacity-35"
              >
                <ArrowUp size={16} />
              </button>
            </div>
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
          <p className="mt-2 text-xs text-ink-soft">Sent. Waiting for the assistant…</p>
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
      <div className="mx-auto flex max-w-3xl items-center gap-2 rounded-xl border border-line bg-surface-raised px-3 py-1.5 text-sm">
        <MessageCircleQuestionMark size={14} className="shrink-0 text-accent" />
        <span className="min-w-0 flex-1 break-words">{question}</span>
        <button
          type="button"
          onClick={onAnswer}
          className="shrink-0 rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90"
        >
          Answer
        </button>
      </div>
    </div>
  );
}

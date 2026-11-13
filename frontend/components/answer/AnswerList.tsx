"use client";

import { ArrowUp } from "lucide-react";
import type { KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { BADGE, OPTION } from "@/components/answer/answerStyles";

const OPTION_KEY = /^[1-9]$/;

interface AnswerListProps {
  options: string[];
  disabled: boolean;
  autoFocus: boolean;
  onAnswer: (text: string) => void;
}

/** A question's options and the person's own words as one list: a number picks, typing fills the last row. */
export function AnswerList({ options, disabled, autoFocus, onAnswer }: AnswerListProps) {
  const [draft, setDraft] = useState("");
  const list = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus) list.current?.focus();
  }, [autoFocus]);

  const submit = () => {
    const text = draft.trim();
    if (text && !disabled) onAnswer(text);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (disabled || event.target === input.current) return;
    if (event.metaKey || event.ctrlKey || event.altKey || event.nativeEvent.isComposing) return;
    const option = OPTION_KEY.test(event.key) ? options[Number(event.key) - 1] : undefined;
    if (option !== undefined) {
      event.preventDefault();
      onAnswer(option);
      return;
    }
    if (event.key.length === 1) input.current?.focus();
  };

  return (
    <div ref={list} tabIndex={-1} onKeyDown={handleKeyDown} className="flex flex-col gap-2 outline-none">
      {options.map((label, index) => (
        <button
          key={index}
          type="button"
          disabled={disabled}
          onClick={() => onAnswer(label)}
          className={OPTION}
        >
          <span className={BADGE}>{index + 1}</span>
          <span className="min-w-0 break-words">{label}</span>
        </button>
      ))}
      <div className="flex items-center gap-2.5 rounded-lg border border-line bg-surface py-1 pl-3 pr-1 transition focus-within:border-accent">
        {options.length > 0 && <span className={BADGE}>{options.length + 1}</span>}
        <input
          ref={input}
          type="text"
          value={draft}
          disabled={disabled}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              submit();
            }
          }}
          aria-label="Your answer"
          placeholder={options.length > 0 ? "Something else…" : "Your answer"}
          className="min-w-0 flex-1 bg-transparent py-1 text-sm font-medium outline-none placeholder:font-normal placeholder:text-ink-soft"
        />
        <button
          type="button"
          onClick={submit}
          disabled={disabled || !draft.trim()}
          aria-label="Send answer"
          title="Send answer"
          className="flex size-7 shrink-0 items-center justify-center rounded-md bg-action text-on-action transition hover:opacity-90 disabled:opacity-35"
        >
          <ArrowUp size={15} />
        </button>
      </div>
    </div>
  );
}

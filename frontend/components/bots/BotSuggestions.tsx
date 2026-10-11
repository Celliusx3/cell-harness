"use client";

import { BADGE, OPTION } from "@/components/answer/QuestionPanel";

interface BotSuggestion {
  label: string;
  starter: string;
}

const SUGGESTIONS: readonly BotSuggestion[] = [
  { label: "Research & writing", starter: "A bot that researches " },
  { label: "Markets & money", starter: "A bot that keeps an eye on " },
  { label: "Places & food", starter: "A bot that finds places to " },
  { label: "Learning", starter: "A bot that teaches me " },
];

/** The kinds of bot to start from; a pick hands back its sentence to finish. */
export function BotSuggestions({ onPick }: { onPick: (starter: string) => void }) {
  return (
    <div className="flex flex-col gap-2">
      {SUGGESTIONS.map((suggestion, index) => (
        <button
          key={suggestion.label}
          type="button"
          onClick={() => onPick(suggestion.starter)}
          className={OPTION}
        >
          <span className={BADGE}>{index + 1}</span>{" "}
          <span className="flex min-w-0 flex-col break-words">
            <span>{suggestion.label}</span>
            <span className="font-normal text-ink-soft">{suggestion.starter}…</span>
          </span>
        </button>
      ))}
    </div>
  );
}

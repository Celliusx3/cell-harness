"use client";

import { ArrowUp, Square } from "lucide-react";
import { useRef, useState } from "react";

interface Props {
  running: boolean;
  onSend(prompt: string): void;
  onStop(): void;
  autoFocus?: boolean;
}

/**
 * The composer, and the stop button in its place while a turn runs.
 *
 * One control, two states, because "send" and "stop" are never both useful: a
 * second message during a turn is refused with a 409, so offering it would be
 * offering a button that errors.
 */
export function Composer({ running, onSend, onStop, autoFocus }: Props) {
  const [draft, setDraft] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    // Trimmed here as well as validated at the edge — the backend rejects a
    // whitespace-only prompt with a 422, and a UI that can produce one is a UI
    // that shows the user an error it could have prevented.
    const prompt = draft.trim();
    if (!prompt || running) return;
    onSend(prompt);
    setDraft("");
    box.current?.focus();
  };

  return (
    <div className="border-t border-line bg-surface px-4 py-4">
      <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-line bg-surface-sunken p-2 focus-within:border-accent">
        <textarea
          ref={box}
          autoFocus={autoFocus}
          rows={1}
          value={draft}
          disabled={running}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            // Enter sends, Shift+Enter breaks the line — and `isComposing`
            // guards an IME: committing a candidate fires Enter too, and
            // sending there would cut a half-typed word.
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              submit();
            }
          }}
          placeholder={running ? "Working…" : "Send a message"}
          className="max-h-48 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-ink-soft disabled:opacity-60"
        />
        {running ? (
          <button
            onClick={onStop}
            aria-label="Stop"
            className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-danger text-white transition hover:opacity-90"
          >
            <Square size={14} fill="currentColor" />
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={!draft.trim()}
            aria-label="Send"
            className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent text-white transition hover:opacity-90 disabled:opacity-35"
          >
            <ArrowUp size={16} />
          </button>
        )}
      </div>
    </div>
  );
}

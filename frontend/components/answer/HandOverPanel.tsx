"use client";

import { Hand } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { handOverOf } from "@/components/answer/handOver";
import { BADGE, FADE_ABOVE, OPTION } from "@/components/answer/QuestionPanel";
import { useClientTool } from "@/components/answer/useClientTool";
import { releaseControl } from "@/components/computer/screen";
import type { ToolItem } from "@/components/conversation/timelineItems";
import type { HandOverAnswer } from "@/lib/types";

const COMPUTER_PAGE = "/computer";
const UNREADABLE_NOTICE = "This request could not be read. Ask the assistant what it needs.";

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : "The answer could not be sent.";
}

/** A waiting `hand_over`: open the computer, then I'm done or Skip; folded only when `onFold` is given. */
export function HandOverPanel({
  item,
  conversationId,
  onAnswered,
  onFold,
}: {
  item: ToolItem;
  conversationId: string;
  onAnswered: () => void;
  onFold?: () => void;
}) {
  const { phase, setPhase, send } = useClientTool<HandOverAnswer>({
    item,
    conversationId,
    onAnswered,
  });
  const [problem, setProblem] = useState<string | null>(null);
  const panel = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const asked = handOverOf(item);

  useEffect(() => {
    panel.current?.focus();
  }, []);

  const answer = async (finished: boolean) => {
    setProblem(null);
    setPhase("working");
    await releaseControl().catch(() => undefined);
    try {
      await send({ kind: "shared", data: { finished } });
    } catch (err: unknown) {
      setProblem(messageOf(err));
      setPhase("asking");
    }
  };

  const keys: Record<string, () => void> = {
    "1": () => router.push(COMPUTER_PAGE),
    "2": () => void answer(true),
    "3": () => void answer(false),
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (phase !== "asking") return;
    if (event.key === "Escape" && onFold !== undefined && !event.nativeEvent.isComposing) {
      event.preventDefault();
      onFold();
      return;
    }
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const action = keys[event.key];
    if (action === undefined) return;
    event.preventDefault();
    action();
  };

  return (
    <div className={`relative bg-surface px-4 pb-5 pt-2 ${FADE_ABOVE}`}>
      <div
        ref={panel}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="mx-auto max-w-3xl rounded-2xl border border-line bg-surface-raised p-3 shadow-sm outline-none"
      >
        <div className="flex items-center gap-2 text-sm">
          <Hand size={14} className="shrink-0 text-accent" />
          <span className="font-medium">Needs you</span>
        </div>
        {asked === null ? (
          <p className="mt-2 break-words text-sm text-danger">{UNREADABLE_NOTICE}</p>
        ) : (
          <p className="mt-2 break-words text-sm">{asked.step}</p>
        )}
        {problem !== null && <p className="mt-2 break-words text-xs text-danger">{problem}</p>}
        {phase === "asking" ? (
          <>
            <div className="mt-3 flex flex-col gap-2">
              <Link href={COMPUTER_PAGE} className={OPTION}>
                <span className={BADGE}>1</span> <span>Open computer</span>
              </Link>
              <button type="button" onClick={() => void answer(true)} className={OPTION}>
                <span className={BADGE}>2</span> <span>I&apos;m done</span>
              </button>
              <button type="button" onClick={() => void answer(false)} className={OPTION}>
                <span className={BADGE}>3</span> <span>Skip</span>
              </button>
            </div>
            {onFold !== undefined && (
              <div className="mt-2 flex items-center gap-1.5 text-xs text-ink-soft">
                <button type="button" onClick={onFold} className="transition hover:text-ink">
                  Type a message instead
                </button>
                <kbd className="rounded border border-line px-1 font-sans">Esc</kbd>
              </div>
            )}
          </>
        ) : (
          <p className="mt-2 text-xs text-ink-soft">
            {phase === "working" ? "Handing the computer back…" : "Sent. Waiting for the assistant…"}
          </p>
        )}
      </div>
    </div>
  );
}

/** The folded hand-over, a line above the message box. */
export function HandOverBar({ step, onShow }: { step: string; onShow: () => void }) {
  return (
    <div className={`relative z-10 bg-surface px-4 pt-2 ${FADE_ABOVE}`}>
      <div className="mx-auto flex max-w-3xl items-center gap-2 rounded-xl border border-line bg-surface-raised px-3 py-1.5 text-sm">
        <Hand size={14} className="shrink-0 text-accent" />
        <span className="min-w-0 flex-1 break-words">{`Needs you: ${step}`}</span>
        <button
          type="button"
          onClick={onShow}
          className="shrink-0 rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90"
        >
          Show
        </button>
      </div>
    </div>
  );
}

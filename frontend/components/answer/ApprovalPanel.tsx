"use client";

import { ShieldQuestion } from "lucide-react";
import type { KeyboardEvent } from "react";
import { useEffect, useRef } from "react";

import { approvalTitle } from "@/components/answer/approval";
import { BADGE, FADE_ABOVE, OPTION } from "@/components/answer/QuestionPanel";
import { useClientTool } from "@/components/answer/useClientTool";
import type { ToolItem } from "@/components/conversation/timelineItems";
import { Arguments } from "@/components/conversation/ToolCard";
import { humanise } from "@/lib/toolName";
import type { Decision } from "@/lib/types";

const OPTIONS: { label: string; decision: Decision }[] = [
  { label: "Allow once", decision: { kind: "approved", scope: "once" } },
  { label: "Allow for this conversation", decision: { kind: "approved", scope: "conversation" } },
  { label: "Always allow", decision: { kind: "approved", scope: "always" } },
  { label: "Deny", decision: { kind: "denied" } },
];

/** A gated call waiting on the person, answered by an option or its number key; skipped only when `onSkip` is given. */
export function ApprovalPanel({
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
  const { phase, send } = useClientTool<never>({ item, conversationId, onAnswered });
  const panel = useRef<HTMLDivElement>(null);
  const { server, label } = humanise(item.call.name);

  useEffect(() => {
    panel.current?.focus();
  }, []);

  const decide = (decision: Decision) => void send(decision);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (phase !== "asking") return;
    if (event.key === "Escape" && onSkip !== undefined && !event.nativeEvent.isComposing) {
      event.preventDefault();
      onSkip();
      return;
    }
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const option = OPTIONS.find((_, index) => String(index + 1) === event.key);
    if (option === undefined) return;
    event.preventDefault();
    decide(option.decision);
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
          <ShieldQuestion size={14} className="shrink-0 text-accent" />
          <span className="min-w-0 break-words font-medium">{label}</span>
          {server !== null && (
            <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
              {server}
            </span>
          )}
        </div>
        <div className="mt-2 space-y-2">
          <Arguments raw={item.call.arguments} tool={item.call.name} />
        </div>
        {phase === "asking" ? (
          <>
            <div className="mt-3 flex flex-col gap-2">
              {OPTIONS.map((option, index) => (
                <button
                  key={option.label}
                  type="button"
                  onClick={() => decide(option.decision)}
                  className={OPTION}
                >
                  <span className={BADGE}>{index + 1}</span>{" "}
                  <span className="min-w-0 break-words">{option.label}</span>
                </button>
              ))}
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

/** The skipped approval, folded to a line above the message box. */
export function ApprovalBar({ item, onReview }: { item: ToolItem; onReview: () => void }) {
  return (
    <div className={`relative z-10 bg-surface px-4 pt-2 ${FADE_ABOVE}`}>
      <div className="mx-auto flex max-w-3xl items-center gap-2 rounded-xl border border-line bg-surface-raised px-3 py-1.5 text-sm">
        <ShieldQuestion size={14} className="shrink-0 text-accent" />
        <span className="min-w-0 flex-1 break-words">{`${approvalTitle(item)} wants to run`}</span>
        <button
          type="button"
          onClick={onReview}
          className="shrink-0 rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90"
        >
          Review
        </button>
      </div>
    </div>
  );
}

/** The conversation's one-line record of a gated call still waiting on the person. */
export function ApprovalRecord({ item }: { item: ToolItem }) {
  return (
    <div className="flex items-start gap-2 text-xs text-ink-soft">
      <ShieldQuestion size={14} className="mt-px shrink-0 text-accent" />
      <span className="min-w-0 break-words">{`${approvalTitle(item)} · waiting for you`}</span>
    </div>
  );
}

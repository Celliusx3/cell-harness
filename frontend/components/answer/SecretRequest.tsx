"use client";

import { KeyRound } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";
import { z } from "zod";

import type { ClientToolProps } from "@/components/answer/useClientTool";
import type { ToolItem } from "@/components/conversation/timelineItems";
import { ApiError, saveSecret } from "@/lib/api";

const SecretAsk = z.object({ name: z.string(), origin: z.url(), label: z.string() });
type SecretAsk = z.infer<typeof SecretAsk>;

type Phase = "asking" | "saving" | "sent";

/** The card for an `ask_for_secret` call: the key is typed here, sent once, and never shown again. */
export function SecretRequest({ item, conversationId, onAnswered }: ClientToolProps) {
  const [draft, setDraft] = useState("");
  const [phase, setPhase] = useState<Phase>("asking");
  const [problem, setProblem] = useState<string | null>(null);
  const ask = askOf(item.call.arguments);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = draft;
    setDraft("");
    setProblem(null);
    setPhase("saving");
    try {
      await saveSecret(conversationId, item.call.id, value);
      setPhase("sent");
      onAnswered();
    } catch (err) {
      setProblem(refusalReason(err));
      setPhase("asking");
    }
  };

  return (
    <div className="rounded-xl border border-accent/40 bg-accent-soft px-3 py-2.5 text-sm">
      <div className="flex items-center gap-2">
        <KeyRound size={14} className="shrink-0 text-accent" />
        <span className="min-w-0 break-words font-medium">{headline(item, ask, phase)}</span>
      </div>
      {item.result === null && phase === "asking" && (
        <>
          {ask !== null && (
            <p className="mt-1 break-words text-xs text-ink-soft">
              {`Sent only to ${new URL(ask.origin).host}. The assistant never sees it.`}
            </p>
          )}
          <form onSubmit={(event) => void handleSubmit(event)} className="mt-2 flex gap-2">
            <input
              type="password"
              autoComplete="off"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              aria-label={ask?.label ?? "Key"}
              placeholder="Paste the key here"
              className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2.5 py-1 text-sm outline-none transition focus:border-accent"
            />
            <button
              type="submit"
              disabled={!draft}
              className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-35"
            >
              Save
            </button>
          </form>
        </>
      )}
      {problem !== null && <p className="mt-2 break-words text-xs text-danger">{problem}</p>}
    </div>
  );
}

function askOf(raw: string): SecretAsk | null {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  const parsed = SecretAsk.safeParse(value);
  return parsed.success ? parsed.data : null;
}

function headline(item: ToolItem, ask: SecretAsk | null, phase: Phase): string {
  if (item.result === null) {
    if (phase === "saving") return "Saving…";
    if (phase === "sent") return "Saved. Waiting for the assistant…";
    return ask?.label ?? "The assistant needs a key.";
  }
  switch (item.error) {
    case null:
      return `Saved as ${ask?.name ?? "a key"}.`;
    case "SKIPPED":
      return "Skipped. You continued without saving.";
    default:
      return "Key request cancelled.";
  }
}

function refusalReason(err: unknown): string {
  if (!(err instanceof ApiError)) return "The key could not be saved. Try again.";
  switch (err.status) {
    case 422:
      return err.message;
    case 404:
      return "This request was already answered or skipped.";
    case 409:
      return "The assistant is busy. Try again in a moment.";
    default:
      return err.message;
  }
}

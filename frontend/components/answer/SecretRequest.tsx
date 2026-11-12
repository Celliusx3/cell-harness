"use client";

import { KeyRound } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import { askedModel, askOf, destinationNote, secretEntry, type SecretAsk } from "@/components/answer/secretAsk";
import type { ClientToolProps } from "@/components/answer/useClientTool";
import type { ToolItem } from "@/components/conversation/timelineItems";
import { Field, INPUT_CLASSES, VisionCheck } from "@/components/credentials/CredentialFields";
import { ApiError, saveSecret } from "@/lib/api";
import type { ModelDetails } from "@/lib/credentials";

type Phase = "asking" | "saving" | "sent";

/** The card for an `ask_for_secret` call: the key is typed here, sent once, and never shown again. */
export function SecretRequest({ item, conversationId, onAnswered }: ClientToolProps) {
  const [draft, setDraft] = useState("");
  const [phase, setPhase] = useState<Phase>("asking");
  const [problem, setProblem] = useState<string | null>(null);
  const ask = askOf(item.call.arguments);
  const [model, setModel] = useState<ModelDetails | null>(() => askedModel(ask));

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = draft;
    setDraft("");
    setProblem(null);
    setPhase("saving");
    try {
      await saveSecret(conversationId, item.call.id, secretEntry(value, model));
      setPhase("sent");
      onAnswered();
    } catch (err) {
      setProblem(refusalReason(err));
      setPhase("asking");
    }
  };

  return (
    <div className="rounded-xl border border-attention/40 bg-attention-soft px-3 py-2.5 text-sm">
      <div className="flex items-center gap-2">
        <KeyRound size={14} className="shrink-0 text-attention" />
        <span className="min-w-0 break-words font-medium">{headline(item, ask, phase)}</span>
      </div>
      {item.result === null && phase === "asking" && (
        <>
          {ask !== null && <p className="mt-1 break-words text-xs text-ink-soft">{destinationNote(ask)}</p>}
          {model !== null && <ModelFields callId={item.call.id} model={model} onChange={setModel} />}
          <form onSubmit={(event) => void handleSubmit(event)} className="mt-2 flex gap-2">
            <input
              type="password"
              autoComplete="off"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              aria-label={ask?.label ?? "Key"}
              placeholder={isPlatform(ask) ? "Paste the token here" : "Paste the key here"}
              className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2.5 py-1 text-sm outline-none transition focus:border-accent"
            />
            <button
              type="submit"
              disabled={!draft}
              className="rounded-lg bg-action px-3 py-1 text-xs font-medium text-on-action transition hover:opacity-90 disabled:opacity-35"
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

interface ModelFieldsProps {
  callId: string;
  model: ModelDetails;
  onChange: (model: ModelDetails) => void;
}

/** The endpoint, model and vision the assistant filled in, editable before the key is saved. */
function ModelFields({ callId, model, onChange }: ModelFieldsProps) {
  return (
    <div className="mt-2 grid gap-2">
      <Field label="Endpoint" htmlFor={`endpoint-${callId}`}>
        <input
          id={`endpoint-${callId}`}
          value={model.base_url}
          onChange={(event) => onChange({ ...model, base_url: event.target.value })}
          inputMode="url"
          autoComplete="off"
          className={INPUT_CLASSES}
        />
      </Field>
      <Field label="Model" htmlFor={`model-${callId}`}>
        <input
          id={`model-${callId}`}
          value={model.model}
          onChange={(event) => onChange({ ...model, model: event.target.value })}
          autoComplete="off"
          className={`font-mono ${INPUT_CLASSES}`}
        />
      </Field>
      <VisionCheck id={`vision-${callId}`} isChecked={model.vision} onChange={(vision) => onChange({ ...model, vision })} />
    </div>
  );
}

function isPlatform(ask: SecretAsk | null): boolean {
  return ask?.kind === "telegram" || ask?.kind === "discord";
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
  return err.status === 404 ? "This request was already answered or skipped." : err.message;
}

"use client";

import { useState, type FormEvent } from "react";

import { ApiError } from "@/lib/api";
import type { BotDraft } from "@/lib/types";

interface BotFormProps {
  initial: BotDraft;
  onSave: (draft: BotDraft) => Promise<void>;
  onDelete: (() => Promise<void>) | null;
}

/** A bot's name and instructions, saved whole. */
export function BotForm({ initial, onSave, onDelete }: BotFormProps) {
  const [name, setName] = useState(initial.name);
  const [instructions, setInstructions] = useState(initial.instructions);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>, fallback: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : fallback);
      setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run(() => onSave({ name, instructions }), "Could not save the bot.");
  }

  return (
    <form onSubmit={submit} className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-5">
      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-ink-soft" htmlFor="bot-name">
          Name
        </label>
        <input
          id="bot-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="rounded-lg border border-line bg-surface-sunken px-2.5 py-1.5 text-sm outline-none focus:border-accent"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-ink-soft" htmlFor="bot-instructions">
          Instructions
        </label>
        <textarea
          id="bot-instructions"
          value={instructions}
          onChange={(event) => setInstructions(event.target.value)}
          rows={14}
          className="resize-y rounded-xl border border-line bg-surface-sunken p-3 text-sm outline-none focus:border-accent"
        />
      </div>

      {error && (
        <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <div className="flex items-center gap-2">
        {onDelete !== null && (
          <button
            type="button"
            onClick={() => void run(onDelete, "Could not delete the bot.")}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-danger/40 bg-surface px-2.5 py-1 text-xs font-medium text-danger hover:bg-danger-soft disabled:opacity-35"
          >
            Delete
          </button>
        )}
        <button
          type="submit"
          disabled={busy}
          className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-35"
        >
          Save
        </button>
      </div>
    </form>
  );
}

"use client";

import { useState, type FormEvent } from "react";

import { ApiError } from "@/lib/api";
import type { ModelOption } from "@/lib/credentials";
import type { Bot, BotEdit } from "@/lib/types";

const NO_MODEL = "";

interface BotFormProps {
  initial: Bot;
  models: ModelOption[];
  onSave: (edit: BotEdit) => Promise<void>;
  onArchive: (() => Promise<void>) | null;
}

/** A bot's name, instructions and model, saved whole. */
export function BotForm({ initial, models, onSave, onArchive }: BotFormProps) {
  const [name, setName] = useState(initial.name);
  const [instructions, setInstructions] = useState(initial.instructions);
  const [model, setModel] = useState(initial.model_credential ?? NO_MODEL);
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
    const modelCredential = model === NO_MODEL ? null : model;
    void run(() => onSave({ name, instructions, model: modelCredential }), "Could not save the bot.");
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

      <ModelSelect models={models} value={model} onChange={setModel} />

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
        {onArchive !== null && (
          <button
            type="button"
            onClick={() => void run(onArchive, "Could not archive the bot.")}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink-soft transition hover:bg-line hover:text-ink disabled:opacity-35"
          >
            Archive
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

interface ModelSelectProps {
  models: ModelOption[];
  value: string;
  onChange: (value: string) => void;
}

function ModelSelect({ models, value, onChange }: ModelSelectProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs text-ink-soft" htmlFor="bot-model">
        Model
      </label>
      <select
        id="bot-model"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-lg border border-line bg-surface-sunken px-2.5 py-1.5 text-sm outline-none focus:border-accent"
      >
        <option value={NO_MODEL}>No model</option>
        {models.map((option) => (
          <option key={option.name} value={option.name}>
            {`${option.name} — ${option.model} at ${option.host}`}
          </option>
        ))}
      </select>
    </div>
  );
}

"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import { ApiError, deleteBot, restoreBot } from "@/lib/api";
import type { Bot } from "@/lib/types";

interface ArchivedBotsProps {
  bots: Bot[];
  onChange: () => void;
}

/** The archived bots, collapsed under their count; each restored, or deleted for good. */
export function ArchivedBots({ bots, onChange }: ArchivedBotsProps) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>, fallback: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChange();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : fallback);
    } finally {
      setBusy(false);
    }
  }

  function restore(bot: Bot) {
    void run(() => restoreBot(bot.id), `Could not restore ${bot.name}.`);
  }

  function remove(bot: Bot) {
    if (!window.confirm(`Delete ${bot.name} and its chat for good?`)) return;
    void run(() => deleteBot(bot.id), `Could not delete ${bot.name}.`);
  }

  return (
    <section className="border-t border-line pt-2">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        className="flex w-full items-center justify-between rounded-md px-2 py-1 text-xs font-medium text-ink-soft transition hover:bg-line hover:text-ink"
      >
        <span className="flex items-center gap-1">
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          Archived
        </span>
        <span>{bots.length}</span>
      </button>
      {open && (
        <ul className="mt-0.5 space-y-0.5">
          {bots.map((bot) => (
            <li key={bot.id} className="flex items-center gap-1 rounded-md px-2 py-1.5">
              <span className="min-w-0 flex-1 truncate text-sm text-ink-soft">{bot.name}</span>
              <button
                type="button"
                aria-label={`Restore ${bot.name}`}
                onClick={() => restore(bot)}
                disabled={busy}
                className="rounded-md px-1.5 py-0.5 text-xs text-ink-soft transition hover:bg-line hover:text-ink disabled:opacity-35"
              >
                Restore
              </button>
              <button
                type="button"
                aria-label={`Delete ${bot.name}`}
                onClick={() => remove(bot)}
                disabled={busy}
                className="rounded-md px-1.5 py-0.5 text-xs text-danger transition hover:bg-danger-soft disabled:opacity-35"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="px-2 pt-1 text-xs text-danger">{error}</p>}
    </section>
  );
}

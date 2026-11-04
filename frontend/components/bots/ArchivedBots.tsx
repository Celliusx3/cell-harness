"use client";

import { useState } from "react";

import { BotsSection } from "@/components/bots/BotList";
import { ApiError, deleteBot, restoreBot } from "@/lib/api";
import type { Bot } from "@/lib/types";

interface ArchivedBotsProps {
  bots: Bot[];
  onChange: () => void;
}

/** The archived bots, each restored, or deleted for good. */
export function ArchivedBots({ bots, onChange }: ArchivedBotsProps) {
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
    <div>
      <BotsSection title="Archived">
        {bots.map((bot) => (
          <li key={bot.id} className="flex items-center gap-1 px-3 py-2">
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
      </BotsSection>
      {error && <p className="pt-1 text-xs text-danger">{error}</p>}
    </div>
  );
}

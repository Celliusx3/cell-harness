"use client";

import { useEffect, useState } from "react";

import { ApiError, listSecrets, setBotSecrets } from "@/lib/api";
import type { Bot, SecretSummary } from "@/lib/types";

/** Every saved key, ticked when this bot may use it; a tick is saved at once. */
export function BotKeys({ bot }: { bot: Bot }) {
  const [keys, setKeys] = useState<SecretSummary[]>([]);
  const [allowed, setAllowed] = useState<string[]>(bot.secret_names);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listSecrets()
      .then((listed) => {
        if (!cancelled) setKeys(listed);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load keys.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function toggle(name: string, checked: boolean) {
    const names = keys
      .map((key) => key.name)
      .filter((candidate) => (candidate === name ? checked : allowed.includes(candidate)));
    setBusy(true);
    setError(null);
    try {
      setAllowed((await setBotSecrets(bot.id, names)).secret_names);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not change the bot's keys.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-1.5 px-6 pb-5">
      <h2 className="text-xs text-ink-soft">Keys this bot can use</h2>
      {keys.length === 0 ? (
        <p className="text-sm text-ink-soft">No keys saved yet.</p>
      ) : (
        <ul className="divide-y divide-line rounded-xl border border-line bg-surface-sunken">
          {keys.map((key) => (
            <li key={key.name}>
              <label className="flex items-center gap-2 px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={allowed.includes(key.name)}
                  disabled={busy}
                  onChange={(event) => void toggle(key.name, event.target.checked)}
                  className="accent-accent"
                />
                <span className="font-medium">{key.name}</span>
                <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
                  {new URL(key.origin).host}
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
    </section>
  );
}

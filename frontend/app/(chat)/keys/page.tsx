"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, deleteSecret, listSecrets } from "@/lib/api";
import type { SecretSummary } from "@/lib/types";

/** Every saved key, the bots allowed to use it, and a way to remove it. */
export default function KeysPage() {
  const [keys, setKeys] = useState<SecretSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setKeys(await listSecrets());
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not load keys.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const remove = async (name: string) => {
    try {
      await deleteSecret(name);
    } catch (err: unknown) {
      const alreadyGone = err instanceof ApiError && err.status === 404;
      if (!alreadyGone) {
        setError(err instanceof ApiError ? err.message : "Could not remove the key.");
        return;
      }
    }
    await refresh();
  };

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">Keys</h1>
        <span className="shrink-0 text-xs text-ink-soft">{keys.length} saved</span>
      </header>

      {error && (
        <div className="border-b border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {keys.length === 0 ? (
          <p className="text-sm text-ink-soft">
            No keys saved yet. A bot asks for one on a card when it needs it.
          </p>
        ) : (
          <ul className="max-w-2xl divide-y divide-line rounded-xl border border-line bg-surface-sunken">
            {keys.map((key) => (
              <KeyRow key={key.name} secret={key} onRemove={() => void remove(key.name)} />
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

function KeyRow({ secret, onRemove }: { secret: SecretSummary; onRemove: () => void }) {
  return (
    <li className="flex items-center gap-2 px-3 py-2 text-sm">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">{secret.name}</span>
          <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
            {new URL(secret.origin).host}
          </span>
        </div>
        <p className="mt-0.5 break-words text-xs text-ink-soft">{usedBy(secret)}</p>
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="shrink-0 rounded-lg border border-line bg-surface px-3 py-1 text-xs font-medium transition hover:bg-surface-sunken"
      >
        Remove
      </button>
    </li>
  );
}

function usedBy(secret: SecretSummary): string {
  if (secret.bots.length === 0) return "No bot can use it yet";
  return `Used by ${secret.bots.map((bot) => bot.name).join(", ")}`;
}

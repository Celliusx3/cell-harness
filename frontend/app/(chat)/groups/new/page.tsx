"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { refreshSidebar } from "@/components/chat/Sidebar";
import { ApiError, BUILDER_ID, createGroup, listBots } from "@/lib/api";
import type { Bot } from "@/lib/types";

const MIN_MEMBERS = 2;
const MAX_MEMBERS = 6;

/** A new group: its name and two to six bots, who take turns in the order they are picked. */
export default function NewGroupPage() {
  const router = useRouter();
  const [bots, setBots] = useState<Bot[]>([]);
  const [name, setName] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listBots()
      .then((listed) => setBots(listed.filter((bot) => bot.id !== BUILDER_ID)))
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Could not load bots."),
      );
  }, []);

  const toggle = (id: string) =>
    setPicked((current) =>
      current.includes(id) ? current.filter((each) => each !== id) : [...current, id],
    );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const group = await createGroup({ name, member_ids: picked });
      refreshSidebar();
      router.push(`/c/${group.id}`);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not make the group.");
      setBusy(false);
    }
  }

  const ready =
    name.trim() !== "" && picked.length >= MIN_MEMBERS && picked.length <= MAX_MEMBERS;

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">New group</h1>
      </header>
      <form
        onSubmit={(event) => void submit(event)}
        className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-5"
      >
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-ink-soft" htmlFor="group-name">
            Name
          </label>
          <input
            id="group-name"
            value={name}
            autoFocus
            onChange={(event) => setName(event.target.value)}
            className="rounded-lg border border-line bg-surface-sunken px-2.5 py-1.5 text-sm outline-none focus:border-accent"
          />
        </div>

        <fieldset className="flex flex-col gap-1.5">
          <legend className="pb-1.5 text-xs text-ink-soft">
            Members: pick {MIN_MEMBERS} to {MAX_MEMBERS}. They take turns in the order you pick
            them.
          </legend>
          {bots.map((bot) => {
            const at = picked.indexOf(bot.id);
            return (
              <label
                key={bot.id}
                className="flex items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-sm"
              >
                <input type="checkbox" checked={at >= 0} onChange={() => toggle(bot.id)} />
                <span className="min-w-0 flex-1 truncate">{bot.name}</span>
                {at >= 0 && <span className="text-xs text-ink-soft">{at + 1}</span>}
              </label>
            );
          })}
        </fieldset>

        {error && (
          <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="flex items-center">
          <button
            type="submit"
            disabled={busy || !ready}
            className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-35"
          >
            Make group
          </button>
        </div>
      </form>
    </>
  );
}

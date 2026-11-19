"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { DrawerButton } from "@/components/chat/Drawer";
import { refreshSidebar } from "@/components/chat/Sidebar";
import { GroupFields, groupIsReady } from "@/components/groups/GroupFields";
import { ApiError, BUILDER_ID, createGroup, listBots } from "@/lib/api";
import type { Bot } from "@/lib/types";

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

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-4 md:px-6 py-3">
        <DrawerButton />
        <h1 className="min-w-0 truncate text-sm font-medium">New group</h1>
      </header>
      <form
        onSubmit={(event) => void submit(event)}
        className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-5"
      >
        <GroupFields
          name={name}
          onName={setName}
          bots={bots}
          picked={picked}
          onPicked={setPicked}
        />

        {error && (
          <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="flex items-center">
          <button
            type="submit"
            disabled={busy || !groupIsReady(name, picked)}
            className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-action px-3 py-1 text-xs font-medium text-on-action transition hover:opacity-90 disabled:opacity-35"
          >
            Make group
          </button>
        </div>
      </form>
    </>
  );
}

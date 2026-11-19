"use client";

import { useRouter } from "next/navigation";
import { use, useEffect, useState, type FormEvent } from "react";

import { DrawerButton } from "@/components/chat/Drawer";
import { refreshSidebar } from "@/components/chat/Sidebar";
import { useFound } from "@/components/chat/useFound";
import { GroupFields, groupIsReady } from "@/components/groups/GroupFields";
import { ApiError, BUILDER_ID, listBots, listGroups, updateGroup } from "@/lib/api";
import type { Bot, Group } from "@/lib/types";

const FIRST_MEMBER = "";

/** A group's settings: its name, its members in turn order, and its lead. */
export default function GroupSettingsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const group = useFound(listGroups, id, "Could not load groups.");
  const [bots, setBots] = useState<Bot[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listBots()
      .then((listed) => setBots(listed.filter((bot) => bot.id !== BUILDER_ID)))
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Could not load bots."),
      );
  }, []);

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-4 md:px-6 py-3">
        <DrawerButton />
        <h1 className="min-w-0 truncate text-sm font-medium">Group settings</h1>
      </header>
      {error !== null && <p className="px-6 py-5 text-sm text-danger">{error}</p>}
      {group.kind === "failed" && <p className="px-6 py-5 text-sm text-danger">{group.message}</p>}
      {group.kind === "none" && (
        <p className="px-6 py-5 text-sm text-danger">No group has the id {id}.</p>
      )}
      {group.kind === "found" && bots !== null && <GroupSettingsForm group={group.item} bots={bots} />}
    </>
  );
}

function GroupSettingsForm({ group, bots }: { group: Group; bots: Bot[] }) {
  const router = useRouter();
  const [name, setName] = useState(group.name);
  const [picked, setPicked] = useState(() =>
    group.member_ids.filter((member) => bots.some((bot) => bot.id === member)),
  );
  const [lead, setLead] = useState(group.lead_id ?? FIRST_MEMBER);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const leadId = picked.includes(lead) ? lead : null;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await updateGroup(group.id, { name, member_ids: picked, lead_id: leadId });
      refreshSidebar();
      router.push(`/c/${group.id}`);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not save the group.");
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={(event) => void submit(event)}
      className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-5"
    >
      <GroupFields name={name} onName={setName} bots={bots} picked={picked} onPicked={setPicked} />

      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-ink-soft" htmlFor="group-lead">
          Lead
        </label>
        <select
          id="group-lead"
          value={leadId ?? FIRST_MEMBER}
          onChange={(event) => setLead(event.target.value)}
          className="rounded-lg border border-line bg-surface-sunken px-2.5 py-1.5 text-sm outline-none focus:border-accent"
        >
          <option value={FIRST_MEMBER}>First member</option>
          {bots
            .filter((bot) => picked.includes(bot.id))
            .map((bot) => (
              <option key={bot.id} value={bot.id}>
                {bot.name}
              </option>
            ))}
        </select>
      </div>

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
          Save
        </button>
      </div>
    </form>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { use, useEffect, useState, type FormEvent } from "react";

import { DrawerButton } from "@/components/chat/Drawer";
import { refreshSidebar } from "@/components/chat/Sidebar";
import { useFound } from "@/components/chat/useFound";
import { GroupFields, groupIsReady } from "@/components/groups/GroupFields";
import { ApiError, BUILDER_ID, listBots, listGroups, updateGroup } from "@/lib/api";
import { listCredentials, modelOptions, type ModelOption } from "@/lib/credentials";
import type { Bot, Group, ReplySetting } from "@/lib/types";

const FIRST_MEMBER = "";
const NO_MODEL = "";

const REPLY_CHOICES: { value: ReplySetting; label: string }[] = [
  { value: "everyone", label: "Everyone (every member in turn)" },
  { value: "lead", label: "Lead only" },
  { value: "mentions", label: "Only bots you @mention" },
  { value: "auto", label: "Auto (a model picks who answers)" },
];

/** A group's settings: its name, its members in turn order, its lead, and who answers. */
export default function GroupSettingsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const group = useFound(listGroups, id, "Could not load groups.");
  const [bots, setBots] = useState<Bot[] | null>(null);
  const [models, setModels] = useState<ModelOption[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const failed = (fallback: string) => (err: unknown) =>
      setError(err instanceof ApiError ? err.message : fallback);
    listBots()
      .then((listed) => setBots(listed.filter((bot) => bot.id !== BUILDER_ID)))
      .catch(failed("Could not load bots."));
    listCredentials()
      .then((listed) => setModels(modelOptions(listed.credentials)))
      .catch(failed("Could not load models."));
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
      {group.kind === "found" && bots !== null && models !== null && (
        <GroupSettingsForm group={group.item} bots={bots} models={models} />
      )}
    </>
  );
}

interface GroupSettingsFormProps {
  group: Group;
  bots: Bot[];
  models: ModelOption[];
}

function GroupSettingsForm({ group, bots, models }: GroupSettingsFormProps) {
  const router = useRouter();
  const [name, setName] = useState(group.name);
  const [picked, setPicked] = useState(() =>
    group.member_ids.filter((member) => bots.some((bot) => bot.id === member)),
  );
  const [lead, setLead] = useState(group.lead_id ?? FIRST_MEMBER);
  const [reply, setReply] = useState<ReplySetting>(group.reply);
  const [autoModel, setAutoModel] = useState(group.auto_model ?? models[0]?.name ?? NO_MODEL);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const leadId = picked.includes(lead) ? lead : null;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const auto_model = reply === "auto" && autoModel !== NO_MODEL ? autoModel : null;
      await updateGroup(group.id, { name, member_ids: picked, lead_id: leadId, reply, auto_model });
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

      <div className="flex flex-col gap-1.5">
        <label className="text-xs text-ink-soft" htmlFor="group-reply">
          Who answers a plain message
        </label>
        <select
          id="group-reply"
          value={reply}
          onChange={(event) => {
            const chosen = REPLY_CHOICES.find((choice) => choice.value === event.target.value);
            if (chosen) setReply(chosen.value);
          }}
          className="rounded-lg border border-line bg-surface-sunken px-2.5 py-1.5 text-sm outline-none focus:border-accent"
        >
          {REPLY_CHOICES.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </select>
      </div>

      {reply === "auto" && <AutoModelSelect models={models} value={autoModel} onChange={setAutoModel} />}

      {error && (
        <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <div className="flex items-center">
        <button
          type="submit"
          disabled={busy || !groupIsReady(name, picked) || (reply === "auto" && autoModel === NO_MODEL)}
          className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-action px-3 py-1 text-xs font-medium text-on-action transition hover:opacity-90 disabled:opacity-35"
        >
          Save
        </button>
      </div>
    </form>
  );
}

interface AutoModelSelectProps {
  models: ModelOption[];
  value: string;
  onChange: (value: string) => void;
}

/** The saved LLM credential Auto asks who answers each message. */
function AutoModelSelect({ models, value, onChange }: AutoModelSelectProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs text-ink-soft" htmlFor="group-auto-model">
        Model that picks who answers
      </label>
      <select
        id="group-auto-model"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-lg border border-line bg-surface-sunken px-2.5 py-1.5 text-sm outline-none focus:border-accent"
      >
        {models.length === 0 && <option value={NO_MODEL}>No model saved</option>}
        {models.map((option) => (
          <option key={option.name} value={option.name}>
            {`${option.name} — ${option.model} at ${option.host}`}
          </option>
        ))}
      </select>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";

import { type WorkspaceChoice, workspaceChoices } from "@/components/workspace/choices";
import { WorkspacePanel } from "@/components/workspace/WorkspacePanel";
import { ApiError, listBots } from "@/lib/api";
import type { Group } from "@/lib/types";

type Members = { kind: "loading" } | { kind: "loaded"; choices: WorkspaceChoice[] } | { kind: "failed"; message: string };

/** The workspace column beside a chat; a group's also switches to each active member's own workspace. */
export function WorkspaceDock({ chatId, group }: { chatId: string; group: Group | null }) {
  const [chosen, setChosen] = useState(chatId);
  return (
    <section
      aria-label="Workspace files"
      className="hidden min-h-0 w-[26rem] shrink-0 flex-col border-l border-line bg-surface-raised text-sm lg:flex"
    >
      {group !== null && <WorkspaceSwitch group={group} chosen={chosen} onChoose={setChosen} />}
      <WorkspacePanel key={chosen} chatId={chosen} />
    </section>
  );
}

interface WorkspaceSwitchProps {
  group: Group;
  chosen: string;
  onChoose: (chatId: string) => void;
}

function WorkspaceSwitch({ group, chosen, onChoose }: WorkspaceSwitchProps) {
  const members = useMembers(group);
  if (members.kind === "failed") {
    return (
      <p role="alert" className="bg-danger-soft px-3 py-2 break-words text-danger">
        {members.message}
      </p>
    );
  }
  const choices = members.kind === "loaded" ? members.choices : [{ chatId: group.id, name: group.name }];
  return (
    <div className="flex items-center gap-2 border-b border-line px-3 py-1.5">
      <label htmlFor="workspace-of" className="shrink-0 text-xs text-ink-soft">
        Workspace of
      </label>
      <select
        id="workspace-of"
        value={chosen}
        onChange={(event) => onChoose(event.target.value)}
        className="min-w-0 flex-1 rounded-lg border border-line bg-surface-sunken px-2 py-1 text-xs outline-none focus:border-accent"
      >
        {choices.map((choice) => (
          <option key={choice.chatId} value={choice.chatId}>
            {choice.name}
          </option>
        ))}
      </select>
    </div>
  );
}

function useMembers(group: Group): Members {
  const [members, setMembers] = useState<Members>({ kind: "loading" });
  useEffect(() => {
    let current = true;
    listBots()
      .then((bots) => {
        if (current) setMembers({ kind: "loaded", choices: workspaceChoices(group, bots) });
      })
      .catch((err: unknown) => {
        const message = err instanceof ApiError ? err.message : "The group's members could not be loaded.";
        if (current) setMembers({ kind: "failed", message });
      });
    return () => {
      current = false;
    };
  }, [group]);
  return members;
}

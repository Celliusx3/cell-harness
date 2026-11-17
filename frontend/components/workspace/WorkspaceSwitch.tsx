"use client";

import { useEffect, useState } from "react";

import { type WorkspaceChoice, workspaceChoices } from "@/components/workspace/choices";
import { ApiError, listBots } from "@/lib/api";
import type { Group } from "@/lib/types";

type Members = { kind: "loading" } | { kind: "loaded"; choices: WorkspaceChoice[] } | { kind: "failed"; message: string };

interface WorkspaceSwitchProps {
  group: Group;
  chosen: WorkspaceChoice;
  onChoose: (choice: WorkspaceChoice) => void;
}

/** Which workspace a group's files pane shows: the group's own, or an active member's. */
export function WorkspaceSwitch({ group, chosen, onChoose }: WorkspaceSwitchProps) {
  const members = useMembers(group);
  if (members.kind === "failed") {
    return (
      <p role="alert" className="min-w-0 flex-1 break-words text-xs text-danger">
        {members.message}
      </p>
    );
  }
  const choices = members.kind === "loaded" ? members.choices : [{ chatId: group.id, name: group.name }];
  return (
    <select
      aria-label="Workspace of"
      value={chosen.chatId}
      onChange={(event) => {
        const choice = choices.find((each) => each.chatId === event.target.value);
        if (choice !== undefined) onChoose(choice);
      }}
      className="min-w-0 flex-1 rounded-md border border-line bg-surface-sunken px-1.5 py-0.5 text-[11px] font-semibold tracking-[0.06em] text-ink-soft uppercase outline-none focus:border-accent"
    >
      {choices.map((choice) => (
        <option key={choice.chatId} value={choice.chatId}>
          {choice.name}
        </option>
      ))}
    </select>
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

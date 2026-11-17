"use client";

import { useState } from "react";

import type { WorkspaceChoice } from "@/components/workspace/choices";
import { WorkspaceFiles } from "@/components/workspace/WorkspaceFiles";
import { WorkspaceSwitch } from "@/components/workspace/WorkspaceSwitch";
import type { Group } from "@/lib/types";

interface FilesPaneProps {
  chatId: string;
  chatName: string;
  group: Group | null;
}

/** The files pane beside a chat; a group's also switches to each active member's own workspace. */
export function FilesPane({ chatId, chatName, group }: FilesPaneProps) {
  const [chosen, setChosen] = useState<WorkspaceChoice>({ chatId, name: chatName });
  return (
    <section
      aria-label="Files"
      className="hidden min-h-0 min-w-80 flex-1 flex-col border-l border-line bg-surface-raised text-[13px] lg:flex"
    >
      <WorkspaceFiles
        key={chosen.chatId}
        choice={chosen}
        switcher={group === null ? null : <WorkspaceSwitch group={group} chosen={chosen} onChoose={setChosen} />}
      />
    </section>
  );
}

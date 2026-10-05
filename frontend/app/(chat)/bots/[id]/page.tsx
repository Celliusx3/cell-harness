"use client";

import { useRouter } from "next/navigation";
import { use } from "react";

import { BotForm } from "@/components/bots/BotForm";
import { useBot } from "@/components/bots/useBot";
import { refreshSidebar } from "@/components/chat/Sidebar";
import { ASSISTANT_ID, archiveBot, updateBot } from "@/lib/api";
import type { BotDraft } from "@/lib/types";

/** One bot's name and instructions; saving or archiving leaves for a chat. */
export default function EditBotPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const lookup = useBot(id);

  async function save(draft: BotDraft) {
    await updateBot(id, draft);
    router.push(`/c/${id}`);
  }

  async function archive() {
    await archiveBot(id);
    refreshSidebar();
    router.push(`/c/${ASSISTANT_ID}`);
  }

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">Edit bot</h1>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {lookup.kind === "loading" && (
          <p className="px-6 py-6 text-sm text-ink-soft">Loading…</p>
        )}
        {lookup.kind === "none" && (
          <p className="px-6 py-6 text-sm text-danger">No bot has the id {id}.</p>
        )}
        {lookup.kind === "failed" && (
          <p className="px-6 py-6 text-sm text-danger">{lookup.message}</p>
        )}
        {lookup.kind === "found" && (
          <BotForm
            initial={lookup.bot}
            onSave={save}
            onArchive={id === ASSISTANT_ID ? null : archive}
          />
        )}
      </div>
    </>
  );
}

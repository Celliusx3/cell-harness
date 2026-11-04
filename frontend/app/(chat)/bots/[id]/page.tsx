"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use } from "react";

import { BotForm } from "@/components/bots/BotForm";
import { BotKeys } from "@/components/bots/BotKeys";
import { BotLinks } from "@/components/bots/BotLinks";
import { refreshSidebar } from "@/components/chat/Sidebar";
import { useFound } from "@/components/chat/useFound";
import { ASSISTANT_ID, archiveBot, listBots, updateBot } from "@/lib/api";
import type { BotDraft } from "@/lib/types";

/** One bot's name, instructions and keys; saving opens its chat, and archiving opens the Bots page. */
export default function EditBotPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const lookup = useFound(listBots, id, "Could not load bots.");

  async function save(draft: BotDraft) {
    await updateBot(id, draft);
    router.push(`/c/${id}`);
  }

  async function archive() {
    await archiveBot(id);
    refreshSidebar();
    router.push("/bots");
  }

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="flex min-w-0 items-center gap-1.5 text-sm font-medium">
          <Link href="/bots" className="shrink-0 text-ink-soft transition hover:text-ink">
            Bots
          </Link>
          {lookup.kind === "found" && (
            <>
              <ChevronRight size={14} className="shrink-0 text-ink-soft" />
              <span className="truncate">{lookup.item.name}</span>
            </>
          )}
        </h1>
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
          <>
            <BotForm
              initial={lookup.item}
              onSave={save}
              onArchive={id === ASSISTANT_ID ? null : archive}
            />
            <BotKeys bot={lookup.item} />
            <BotLinks bot={lookup.item} />
          </>
        )}
      </div>
    </>
  );
}

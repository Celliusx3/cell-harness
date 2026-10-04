"use client";

import { useRouter } from "next/navigation";

import { BotForm } from "@/components/bots/BotForm";
import { createBot } from "@/lib/api";
import type { BotDraft } from "@/lib/types";

const BLANK: BotDraft = { name: "", instructions: "" };

/** A new bot; saving opens its chat. */
export default function NewBotPage() {
  const router = useRouter();

  async function save(draft: BotDraft) {
    const created = await createBot(draft);
    router.push(`/c/${created.id}`);
  }

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">New bot</h1>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <BotForm initial={BLANK} onSave={save} onDelete={null} />
      </div>
    </>
  );
}

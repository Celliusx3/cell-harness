"use client";

import { Inbox } from "lucide-react";
import Link from "next/link";

import { chatsNeedingYou, useNeedingYou } from "@/components/chat/useNeedingYou";

/** The sidebar's link to the chats with work that waits for a person, with their count; hidden at none. */
export function NeedsYouLink({ current }: { current: boolean }) {
  const { needing } = useNeedingYou();
  const count = needing.kind === "loaded" ? chatsNeedingYou(needing.tickets).length : 0;
  if (count === 0) return null;
  return (
    <Link
      href="/needs-you"
      className={`flex items-center gap-2 rounded-md px-2 py-2 text-sm transition ${
        current ? "bg-accent-soft font-medium text-ink" : "text-ink-soft hover:bg-line hover:text-ink"
      }`}
    >
      <Inbox size={16} className="shrink-0" />
      <span className="min-w-0 flex-1 truncate">Needs you</span>
      <span className="shrink-0 rounded-full bg-attention px-1.5 text-xs font-medium text-surface-raised">
        {count}
      </span>
    </Link>
  );
}

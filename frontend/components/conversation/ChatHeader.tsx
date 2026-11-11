"use client";

import { Ellipsis, Pencil } from "lucide-react";
import Link from "next/link";

import { BotAvatar } from "@/components/conversation/BotAvatar";
import type { Speaker } from "@/components/conversation/timelineItems";
import { type UsageSummary, usageLine } from "@/components/conversation/usage";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const CLEAR_CONFIRMATION =
  "Clear this chat? This permanently removes every message and stops what the bot is doing. The chat stays.";

const COMPACT_DESCRIPTION = "Summarize older messages to free up context";

const ICON_BUTTON =
  "flex size-9 shrink-0 items-center justify-center rounded-lg text-ink-soft transition hover:bg-surface-sunken hover:text-ink";

const MENU_ITEM = "px-2.5 py-2 focus:bg-surface-sunken focus:text-ink";

interface ChatHeaderProps {
  chat: Speaker | null;
  editHref: string | null;
  elapsed: string | null;
  usage: UsageSummary | null;
  canCompact: boolean;
  onCompact(): void;
  onClear(): void;
}

/** The chat's avatar, name and state, with a link to edit the bot and a menu to compact or clear. */
export function ChatHeader({
  chat,
  editHref,
  elapsed,
  usage,
  canCompact,
  onCompact,
  onClear,
}: ChatHeaderProps) {
  return (
    <header className="flex min-h-14 items-center gap-3 border-b border-line px-6 py-2.5">
      {chat !== null && <BotAvatar speaker={chat} />}
      <div className="flex min-w-0 flex-col">
        <h1 className="truncate text-sm font-semibold leading-tight">{chat?.name ?? ""}</h1>
        <div className="flex min-w-0 items-center gap-1.5 text-xs text-ink-soft">
          <ChatState elapsed={elapsed} />
          {usage !== null && (
            <>
              <span aria-hidden>·</span>
              <span className="truncate">{usageLine(usage)}</span>
            </>
          )}
        </div>
      </div>
      <div className="ml-auto flex shrink-0 items-center gap-1">
        {editHref !== null && (
          <Link href={editHref} aria-label="Edit bot" title="Edit bot" className={ICON_BUTTON}>
            <Pencil size={16} />
          </Link>
        )}
        <ChatMenu canCompact={canCompact} onCompact={onCompact} onClear={onClear} />
      </div>
    </header>
  );
}

function ChatState({ elapsed }: { elapsed: string | null }) {
  if (elapsed === null) return <span className="text-xs text-ink-soft">Ready</span>;
  return (
    <span className="flex items-center gap-1.5 text-xs tabular-nums text-ink-soft">
      <span
        aria-hidden
        className="size-1.5 shrink-0 animate-pulse rounded-full bg-accent motion-reduce:animate-none"
      />
      Working · {elapsed}
    </span>
  );
}

function ChatMenu({
  canCompact,
  onCompact,
  onClear,
}: Pick<ChatHeaderProps, "canCompact" | "onCompact" | "onClear">) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="More"
        title="More"
        className={`${ICON_BUTTON} data-popup-open:bg-surface-sunken data-popup-open:text-ink`}
      >
        <Ellipsis size={16} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuItem className={MENU_ITEM} disabled={!canCompact} onClick={onCompact}>
          <span className="flex flex-col">
            Compact
            <span className="text-xs text-ink-soft">{COMPACT_DESCRIPTION}</span>
          </span>
        </DropdownMenuItem>
        <DropdownMenuItem
          className="px-2.5 py-2"
          variant="destructive"
          onClick={() => {
            if (window.confirm(CLEAR_CONFIRMATION)) onClear();
          }}
        >
          Clear chat
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

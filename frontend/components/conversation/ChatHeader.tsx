"use client";

import { Ellipsis, Monitor, Pencil } from "lucide-react";
import Link from "next/link";

import { DrawerButton } from "@/components/chat/Drawer";
import { BotAvatar } from "@/components/conversation/BotAvatar";
import type { Speaker } from "@/components/conversation/timelineItems";
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
  waiting: boolean;
  ticketsAtWork: number;
  canCompact: boolean;
  computer: ComputerToggle | null;
  onCompact(): void;
  onClear(): void;
}

/** Whether the computer is docked beside the chat, and how to dock or close it. */
export interface ComputerToggle {
  docked: boolean;
  onToggle(): void;
}

const DOCK_BUTTON =
  "hidden h-9 shrink-0 items-center gap-2 rounded-[10px] border px-3.5 text-[13px] font-medium transition lg:inline-flex";

/** The chat's avatar, name and state, with a link to edit the bot and a menu to compact or clear. */
export function ChatHeader({
  chat,
  editHref,
  elapsed,
  waiting,
  ticketsAtWork,
  canCompact,
  computer,
  onCompact,
  onClear,
}: ChatHeaderProps) {
  return (
    <header className="flex min-h-14 items-center gap-3 border-b border-line px-4 md:px-6 py-2.5">
      <DrawerButton />
      {chat !== null && <BotAvatar speaker={chat} />}
      <div className="flex min-w-0 flex-col">
        <h1 className="truncate text-sm font-semibold leading-tight">{chat?.name ?? ""}</h1>
        <ChatState elapsed={elapsed} waiting={waiting} ticketsAtWork={ticketsAtWork} />
      </div>
      <div className="ml-auto flex shrink-0 items-center gap-1">
        {computer !== null && <DockButton computer={computer} />}
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

function DockButton({ computer }: { computer: ComputerToggle }) {
  return (
    <button
      type="button"
      aria-pressed={computer.docked}
      title={computer.docked ? "Close the computer" : "Show the computer beside the chat"}
      onClick={computer.onToggle}
      className={
        computer.docked
          ? `${DOCK_BUTTON} border-accent bg-accent-soft text-accent`
          : `${DOCK_BUTTON} border-line text-ink-soft hover:bg-surface-sunken hover:text-ink`
      }
    >
      <Monitor size={16} />
      Computer
    </button>
  );
}

interface ChatStateProps {
  elapsed: string | null;
  waiting: boolean;
  ticketsAtWork: number;
}

function ChatState({ elapsed, waiting, ticketsAtWork }: ChatStateProps) {
  if (waiting) return <span className="text-xs font-medium text-attention">Waiting for you</span>;
  if (elapsed !== null) return <WorkingState label={`Working · ${elapsed}`} />;
  if (ticketsAtWork > 0) {
    return <WorkingState label={`Working on ${ticketsAtWork} ${ticketsAtWork === 1 ? "thing" : "things"}`} />;
  }
  return <span className="text-xs text-ink-soft">Ready</span>;
}

function WorkingState({ label }: { label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-xs tabular-nums text-accent">
      <span
        aria-hidden
        className="size-1.5 shrink-0 animate-pulse rounded-full bg-accent motion-reduce:animate-none"
      />
      {label}
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

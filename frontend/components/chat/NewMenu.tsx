"use client";

import { BotMessageSquare, Plus, Users } from "lucide-react";
import Link from "next/link";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const SIDEBAR_HIGHLIGHT = "focus:bg-line focus:text-ink";

/** The sidebar's one New button: a menu of a new bot and a new group. */
export function NewMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-ink-soft transition hover:bg-line hover:text-ink data-popup-open:bg-line data-popup-open:text-ink">
        <Plus size={16} />
        New
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem className={SIDEBAR_HIGHLIGHT} render={<Link href="/bots/new" />}>
          <BotMessageSquare />
          Bot
        </DropdownMenuItem>
        <DropdownMenuItem className={SIDEBAR_HIGHLIGHT} render={<Link href="/groups/new" />}>
          <Users />
          Group
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

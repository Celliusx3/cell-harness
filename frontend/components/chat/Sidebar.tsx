"use client";

import { BotMessageSquare, Monitor, Settings } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { NeedsYouLink } from "@/components/chat/NeedsYouLink";
import { NewMenu } from "@/components/chat/NewMenu";
import { SidebarLink } from "@/components/chat/SidebarLink";
import { useWorkingChat } from "@/components/chat/workingChat";
import { SERVER as COMPUTER_SERVER } from "@/components/computer/server";
import { rememberChatPath } from "@/components/settings/chatReturn";
import { BUILDER_ID, listBots, listGroups, listServers } from "@/lib/api";
import { type AppEvent, useAppEvent } from "@/lib/appEvents";
import type { Bot, Group } from "@/lib/types";

const STALE = "harness:sidebar-stale";

/** Ask the sidebar to read its bots again. */
export function refreshSidebar(): void {
  window.dispatchEvent(new Event(STALE));
}

/** An app-event handler that calls `reload` when the bots changed, or after a reconnect. */
export function whenBotsMayHaveChanged(reload: () => void): (event: AppEvent) => void {
  return (event) => {
    if (event.type === "bots/changed" || event.type === "app/connected") reload();
  };
}

/** The New button, Needs you, the bots, each a link to its one chat, the groups, other pages. */
export function Sidebar() {
  const [bots, setBots] = useState<Bot[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const pathname = usePathname();
  const params = useParams<{ id?: string }>();
  const currentId = params?.id;
  const workingChat = useWorkingChat();
  const [stale, setStale] = useState(0);
  const [hasComputer, setHasComputer] = useState(false);

  useEffect(() => rememberChatPath(pathname), [pathname]);

  useAppEvent(whenBotsMayHaveChanged(refreshSidebar));

  useEffect(() => {
    const bump = () => setStale((count) => count + 1);
    window.addEventListener(STALE, bump);
    return () => window.removeEventListener(STALE, bump);
  }, []);

  useEffect(() => {
    let cancelled = false;
    listServers()
      .then(({ servers }) => {
        if (!cancelled) setHasComputer(servers.includes(COMPUTER_SERVER));
      })
      .catch(() => setHasComputer(false));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listBots(), listGroups()])
      .then(([listedBots, listedGroups]) => {
        if (cancelled) return;
        setBots(listedBots);
        setGroups(listedGroups);
      })
      .catch(() => {
      });
    return () => {
      cancelled = true;
    };
  }, [pathname, stale]);

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-line bg-surface-sunken">
      <div className="flex items-center justify-between px-4 py-4">
        <span className="text-sm font-semibold tracking-tight">cell-harness</span>
        <NewMenu />
      </div>

      <nav className="min-h-0 flex-1 space-y-4 overflow-y-auto px-2 pb-4">
        <NeedsYouLink current={pathname === "/needs-you"} />
        <SidebarSection title="Bots">
          {bots
            .filter((bot) => bot.id !== BUILDER_ID)
            .map((bot) => (
              <SidebarRow
                key={bot.id}
                href={`/c/${bot.id}`}
                label={bot.name}
                current={bot.id === currentId}
                working={bot.id === workingChat}
              />
            ))}
        </SidebarSection>
        {groups.length > 0 && (
          <SidebarSection title="Groups">
            {groups.map((group) => (
              <SidebarRow
                key={group.id}
                href={`/c/${group.id}`}
                label={group.name}
                current={group.id === currentId}
                working={group.id === workingChat}
              />
            ))}
          </SidebarSection>
        )}
      </nav>

      <div className="space-y-0.5 border-t border-line px-2 py-3">
        <SidebarLink href="/bots" label="Bots" icon={BotMessageSquare} current={pathname === "/bots"} />
        {hasComputer && (
          <SidebarLink href="/computer" label="Computer" icon={Monitor} current={pathname === "/computer"} />
        )}
        <SidebarLink href="/settings" label="Settings" icon={Settings} current={false} />
      </div>
    </aside>
  );
}

function SidebarSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="px-2 pb-1 text-xs font-medium text-ink-soft">{title}</h2>
      <ul className="space-y-0.5">{children}</ul>
    </section>
  );
}

function SidebarRow({
  href,
  label,
  current,
  working,
}: {
  href: string;
  label: string;
  current: boolean;
  working: boolean;
}) {
  return (
    <li>
      <Link
        href={href}
        className={`flex items-center gap-2 rounded-md px-2 py-2 text-sm transition ${
          current ? "bg-accent-soft font-medium text-ink" : "text-ink-soft hover:bg-line hover:text-ink"
        }`}
      >
        <span className="min-w-0 flex-1 truncate">{label}</span>
        {working && (
          <span
            role="img"
            aria-label="Working"
            className="size-[7px] shrink-0 animate-pulse rounded-full bg-accent motion-reduce:animate-none"
          />
        )}
      </Link>
    </li>
  );
}

"use client";

import { Monitor, Settings } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { ArchivedBots } from "@/components/chat/ArchivedBots";
import { NewMenu } from "@/components/chat/NewMenu";
import { SidebarLink } from "@/components/chat/SidebarLink";
import { SERVER as COMPUTER_SERVER } from "@/components/computer/server";
import { BUILDER_ID, listArchivedBots, listBots, listGroups, listServers } from "@/lib/api";
import type { Bot, Group } from "@/lib/types";

const STALE = "harness:sidebar-stale";

/** Ask the sidebar to read its bots again. */
export function refreshSidebar(): void {
  window.dispatchEvent(new Event(STALE));
}

/** The New button, the bots, each a link to its one chat, the groups and the archived bots, then the other pages. */
export function Sidebar() {
  const [bots, setBots] = useState<Bot[]>([]);
  const [archived, setArchived] = useState<Bot[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const pathname = usePathname();
  const params = useParams<{ id?: string }>();
  const currentId = params?.id;
  const [stale, setStale] = useState(0);
  const [hasComputer, setHasComputer] = useState(false);

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
    Promise.all([listBots(), listArchivedBots(), listGroups()])
      .then(([listedBots, listedArchived, listedGroups]) => {
        if (cancelled) return;
        setBots(listedBots);
        setArchived(listedArchived);
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
        <SidebarSection title="Bots">
          {bots
            .filter((bot) => bot.id !== BUILDER_ID)
            .map((bot) => (
              <SidebarRow
                key={bot.id}
                href={`/c/${bot.id}`}
                label={bot.name}
                current={bot.id === currentId}
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
              />
            ))}
          </SidebarSection>
        )}
        {archived.length > 0 && <ArchivedBots bots={archived} onChange={refreshSidebar} />}
      </nav>

      <div className="space-y-0.5 border-t border-line px-2 py-3">
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

function SidebarRow({ href, label, current }: { href: string; label: string; current: boolean }) {
  return (
    <li>
      <Link
        href={href}
        className={`block truncate rounded-md px-2 py-2 text-sm transition ${
          current ? "bg-accent-soft font-medium text-ink" : "text-ink-soft hover:bg-line hover:text-ink"
        }`}
      >
        {label}
      </Link>
    </li>
  );
}

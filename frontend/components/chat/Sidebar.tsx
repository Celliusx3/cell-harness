"use client";

import { BookOpen, BotMessageSquare, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { ArchivedBots } from "@/components/chat/ArchivedBots";
import { listArchivedBots, listBots } from "@/lib/api";
import type { Bot } from "@/lib/types";

const STALE = "harness:sidebar-stale";

/** Ask the sidebar to read its bots again. */
export function refreshSidebar(): void {
  window.dispatchEvent(new Event(STALE));
}

/** The bots, each a link to its one chat, then the archived ones. */
export function Sidebar() {
  const [bots, setBots] = useState<Bot[]>([]);
  const [archived, setArchived] = useState<Bot[]>([]);
  const pathname = usePathname();
  const params = useParams<{ id?: string }>();
  const currentId = params?.id;
  const [stale, setStale] = useState(0);

  useEffect(() => {
    const bump = () => setStale((count) => count + 1);
    window.addEventListener(STALE, bump);
    return () => window.removeEventListener(STALE, bump);
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listBots(), listArchivedBots()])
      .then(([listedBots, listedArchived]) => {
        if (cancelled) return;
        setBots(listedBots);
        setArchived(listedArchived);
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
        <div className="flex items-center gap-0.5">
          <Link
            href="/skills"
            aria-label="Skills"
            className={`rounded-md p-1.5 transition hover:bg-line hover:text-ink ${
              pathname === "/skills" ? "bg-accent-soft text-ink" : "text-ink-soft"
            }`}
          >
            <BookOpen size={18} />
          </Link>
          <Link
            href="/approvals"
            aria-label="Approvals"
            className={`rounded-md p-1.5 transition hover:bg-line hover:text-ink ${
              pathname === "/approvals" ? "bg-accent-soft text-ink" : "text-ink-soft"
            }`}
          >
            <ShieldCheck size={18} />
          </Link>
          <Link
            href="/bots/new"
            aria-label="New bot"
            className={`rounded-md p-1.5 transition hover:bg-line hover:text-ink ${
              pathname === "/bots/new" ? "bg-accent-soft text-ink" : "text-ink-soft"
            }`}
          >
            <BotMessageSquare size={18} />
          </Link>
        </div>
      </div>

      <nav className="min-h-0 flex-1 space-y-4 overflow-y-auto px-2 pb-4">
        <SidebarSection title="Bots">
          {bots.map((bot) => (
            <SidebarRow
              key={bot.id}
              href={`/c/${bot.id}`}
              label={bot.name}
              current={bot.id === currentId}
            />
          ))}
        </SidebarSection>
        {archived.length > 0 && <ArchivedBots bots={archived} onChange={refreshSidebar} />}
      </nav>
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

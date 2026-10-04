"use client";

import { BookOpen, BotMessageSquare, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { listBots, listConversations } from "@/lib/api";
import type { Bot, ConversationSummary } from "@/lib/types";

const STALE = "harness:sidebar-stale";

/** Ask the sidebar to read its bots and chats again, as after a turn that may have changed them. */
export function refreshSidebar(): void {
  window.dispatchEvent(new Event(STALE));
}

function chatsWithoutBot(rows: ConversationSummary[], bots: Bot[]): ConversationSummary[] {
  const botIds = new Set(bots.map((bot) => bot.id));
  return rows.filter((row) => !botIds.has(row.id));
}

/** The bots, then every chat no bot owns. */
export function Sidebar() {
  const [bots, setBots] = useState<Bot[]>([]);
  const [rows, setRows] = useState<ConversationSummary[]>([]);
  const pathname = usePathname();
  const params = useParams<{ id?: string }>();
  const currentId = params?.id;
  const others = useMemo(() => chatsWithoutBot(rows, bots), [rows, bots]);
  const [stale, setStale] = useState(0);

  useEffect(() => {
    const bump = () => setStale((count) => count + 1);
    window.addEventListener(STALE, bump);
    return () => window.removeEventListener(STALE, bump);
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listBots(), listConversations()])
      .then(([listedBots, listedRows]) => {
        if (cancelled) return;
        setBots(listedBots);
        setRows(listedRows);
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
        {others.length > 0 && (
          <SidebarSection title="Other chats">
            {others.map((row) => (
              <SidebarRow
                key={row.id}
                href={`/c/${row.id}`}
                label={row.title || "Untitled"}
                current={row.id === currentId}
              />
            ))}
          </SidebarSection>
        )}
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

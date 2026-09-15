"use client";

import { BookOpen, MessageSquarePlus } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { listConversations } from "@/lib/api";
import type { ConversationSummary } from "@/lib/types";

/**
 * The conversation list.
 *
 * Refetched on navigation rather than kept in a store: the list changes when a
 * conversation is created or its title is stamped, both of which coincide with a
 * navigation, and a cache here would be a second copy of the backend's list to
 * invalidate. `GET /api/conversations` reads one header line per file.
 */
export function Sidebar() {
  const [rows, setRows] = useState<ConversationSummary[]>([]);
  const pathname = usePathname();
  const params = useParams<{ id?: string }>();
  const currentId = params?.id;

  useEffect(() => {
    let cancelled = false;
    listConversations()
      .then((listed) => {
        if (!cancelled) setRows(listed);
      })
      .catch(() => {
        // A sidebar that cannot load is not worth interrupting the conversation
        // for; the main pane reports its own failures.
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

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
            href="/"
            aria-label="New conversation"
            className="rounded-md p-1.5 text-ink-soft transition hover:bg-line hover:text-ink"
          >
            <MessageSquarePlus size={18} />
          </Link>
        </div>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {rows.length === 0 ? (
          <p className="px-2 py-3 text-xs text-ink-soft">No conversations yet.</p>
        ) : (
          <ul className="space-y-0.5">
            {rows.map((row) => (
              <li key={row.id}>
                <Link
                  href={`/c/${row.id}`}
                  className={`block truncate rounded-md px-2 py-2 text-sm transition ${
                    row.id === currentId
                      ? "bg-accent-soft font-medium text-ink"
                      : "text-ink-soft hover:bg-line hover:text-ink"
                  }`}
                >
                  {/* Empty until the opening turn's first flush stamps it, so
                      the fallback is load-bearing rather than defensive. */}
                  {row.title || "Untitled"}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </nav>
    </aside>
  );
}

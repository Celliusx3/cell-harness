"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { use } from "react";

import { McpApp } from "@/components/McpApp";
import type { ToolItem } from "@/lib/timeline";
import { useConversation, useTimeline } from "@/lib/useConversation";

/**
 * One tool call's MCP App, on a page of its own.
 *
 * This is the URL a chat is sent when a result carries an app — a Telegram
 * Mini App button, a Discord link, the "open" link on a browser card — so it
 * has no sidebar and gives the app the whole viewport. Read from the same log
 * as the conversation page: the app's binding and data are on the stored
 * `tool/result`, so there is nothing here that a reload would lose.
 */
export default function AppPage({
  params,
}: {
  params: Promise<{ id: string; call: string }>;
}) {
  const { id, call } = use(params);
  const conversation = useConversation(id);
  const { items } = useTimeline(conversation.events);
  const item = items.find(
    (i): i is ToolItem => i.kind === "tool" && i.call.id === call,
  );

  return (
    <main className="flex min-w-0 flex-1 flex-col">
      <header className="flex items-center gap-3 border-b border-line px-4 py-2">
        <Link
          href={`/c/${id}`}
          className="shrink-0 text-ink-soft"
          aria-label="Back to conversation"
        >
          <ArrowLeft size={16} />
        </Link>
        <h1 className="min-w-0 truncate font-mono text-xs font-medium">
          {item?.call.name ?? "app"}
        </h1>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {conversation.loading ? (
          <p className="px-4 py-6 text-sm text-ink-soft">Loading…</p>
        ) : conversation.error !== null ? (
          <p className="px-4 py-6 text-sm text-danger">{conversation.error}</p>
        ) : item === undefined ? (
          <p className="px-4 py-6 text-sm text-ink-soft">
            No such tool call in this conversation.
          </p>
        ) : item.ui === null ? (
          <p className="px-4 py-6 text-sm text-ink-soft">
            {item.result === null
              ? "Still running…"
              : "This result has no app to show."}
          </p>
        ) : (
          <McpApp item={item} ui={item.ui} />
        )}
      </div>
    </main>
  );
}

"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { use } from "react";

import { McpApp } from "@/components/conversation/McpApp";
import type { ToolItem } from "@/components/conversation/timelineItems";
import { useConversation } from "@/components/conversation/useConversation";
import { useTimeline } from "@/components/conversation/useTimeline";

/** One tool call's MCP App, on a page of its own. */
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

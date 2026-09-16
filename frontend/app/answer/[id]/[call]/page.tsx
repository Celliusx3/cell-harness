"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { use } from "react";

import { CLIENT_TOOLS } from "@/lib/clientTools";
import type { ToolItem } from "@/lib/timeline";
import { useConversation, useTimeline } from "@/lib/useConversation";

/**
 * One client-tool call, on a page of its own.
 *
 * This is the URL a chat without a prompt of its own for the tool is sent — a
 * Discord link, a Telegram link for anything but a location — so the browser
 * can ask instead. Read from the same log as the conversation page: whether
 * the call is still waiting is on the stream, and the answer goes to the same
 * route the conversation's card uses, through the same handler map.
 */
export default function AnswerPage({
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
  const Handler = item === undefined ? undefined : CLIENT_TOOLS[item.call.name];

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
        <h1 className="min-w-0 truncate text-xs font-medium">
          Share your location
        </h1>
      </header>
      <div className="mx-auto w-full max-w-md px-4 py-6">
        {conversation.loading ? (
          <p className="text-sm text-ink-soft">Loading…</p>
        ) : conversation.error !== null ? (
          <p className="text-sm text-danger">{conversation.error}</p>
        ) : item === undefined ? (
          <p className="text-sm text-ink-soft">
            No such request in this conversation.
          </p>
        ) : Handler === undefined ? (
          <p className="text-sm text-ink-soft">
            This page cannot answer {item.call.name}.
          </p>
        ) : (
          <Handler
            item={item}
            conversationId={id}
            onAnswered={conversation.wake}
          />
        )}
      </div>
    </main>
  );
}

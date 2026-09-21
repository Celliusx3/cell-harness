"use client";

import { use } from "react";

import { Composer } from "@/components/Composer";
import { QueuedBubble } from "@/components/Message";
import { Timeline } from "@/components/Timeline";
import { useConversation, useTimeline } from "@/lib/useConversation";

/** One conversation. */
export default function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const conversation = useConversation(id);
  const { items, openTurn, openingMessage } = useTimeline(conversation.events);

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">
          {conversation.title || openingMessage || "Untitled"}
        </h1>
        {conversation.running && (
          <span className="shrink-0 rounded-full bg-accent-soft px-2 py-0.5 text-xs text-ink-soft">
            working
          </span>
        )}
        <button
          type="button"
          onClick={() => void conversation.compact()}
          disabled={conversation.running}
          title="Summarize older messages to free up context"
          className="ml-auto shrink-0 rounded-md border border-line px-2 py-0.5 text-xs text-ink-soft transition hover:text-ink disabled:opacity-40"
        >
          Compact
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {conversation.loading ? (
          <p className="px-6 py-6 text-sm text-ink-soft">Loading…</p>
        ) : (
          <>
            <Timeline
              items={items}
              openTurn={openTurn}
              onAnswered={conversation.wake}
            />
            {conversation.queued.length > 0 && (
              <div className="flex flex-col gap-3 px-6 pb-4">
                {conversation.queued.map((text, index) => (
                  <QueuedBubble key={index} content={text} />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {conversation.error && (
        <p className="border-t border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">
          {conversation.error}
        </p>
      )}

      <Composer
        autoFocus
        running={conversation.running}
        onSend={(prompt) => void conversation.send(prompt)}
        onStop={() => void conversation.stop()}
      />
    </>
  );
}

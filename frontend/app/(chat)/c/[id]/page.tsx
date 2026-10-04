"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useRef, useState } from "react";

import { waitingApproval } from "@/components/answer/approval";
import { ApprovalBar, ApprovalPanel } from "@/components/answer/ApprovalPanel";
import { questionOf, waitingQuestion } from "@/components/answer/question";
import { QuestionBar, QuestionPanel } from "@/components/answer/QuestionPanel";
import { useBot, type BotLookup } from "@/components/bots/useBot";
import { refreshSidebar } from "@/components/chat/Sidebar";
import { Composer } from "@/components/conversation/Composer";
import { QueuedBubble } from "@/components/conversation/Message";
import { Timeline } from "@/components/conversation/Timeline";
import type { TimelineItem, ToolItem } from "@/components/conversation/timelineItems";
import { useConversation } from "@/components/conversation/useConversation";
import { useTimeline } from "@/components/conversation/useTimeline";

type Waiting = { kind: "question"; item: ToolItem } | { kind: "approval"; item: ToolItem };

const CLEAR_CONFIRMATION =
  "Clear this chat? This permanently removes every message and stops what the bot is doing. The chat stays.";

/** One conversation. */
export default function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const conversation = useConversation(id);
  const bot = useBot(id);
  const { items, openTurn, openingMessage } = useTimeline(conversation.events);
  const waiting = useMemo(
    () => (conversation.running ? null : waitingCall(items, openTurn)),
    [conversation.running, items, openTurn],
  );
  const [folded, setFolded] = useState<string | null>(null);
  const wasRunning = useRef(false);

  useEffect(() => {
    if (wasRunning.current && !conversation.running) refreshSidebar();
    wasRunning.current = conversation.running;
  }, [conversation.running]);

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">
          {headerTitle(bot, conversation.title || openingMessage || "Untitled")}
        </h1>
        {conversation.running && (
          <span className="shrink-0 rounded-full bg-accent-soft px-2 py-0.5 text-xs text-ink-soft">
            working
          </span>
        )}
        <div className="ml-auto flex shrink-0 items-center gap-2">
          {bot.kind === "found" && (
            <Link
              href={`/bots/${id}`}
              className="rounded-md border border-line px-2 py-0.5 text-xs text-ink-soft transition hover:text-ink"
            >
              Edit bot
            </Link>
          )}
          <button
            type="button"
            onClick={() => void conversation.compact()}
            disabled={conversation.running}
            title="Summarize older messages to free up context"
            className="rounded-md border border-line px-2 py-0.5 text-xs text-ink-soft transition hover:text-ink disabled:opacity-40"
          >
            Compact
          </button>
          <button
            type="button"
            onClick={() => {
              if (window.confirm(CLEAR_CONFIRMATION)) void conversation.clear();
            }}
            title="Start this chat fresh"
            className="rounded-md border border-line px-2 py-0.5 text-xs text-ink-soft transition hover:text-ink"
          >
            Clear
          </button>
        </div>
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

      {waiting !== null && folded !== waiting.item.call.id ? (
        <WaitingPanel
          key={waiting.item.call.id}
          waiting={waiting}
          conversationId={id}
          onAnswered={conversation.wake}
          onSkip={() => setFolded(waiting.item.call.id)}
        />
      ) : (
        <>
          {waiting !== null && (
            <WaitingBar waiting={waiting} onUnfold={() => setFolded(null)} />
          )}
          <Composer
            autoFocus
            running={conversation.running}
            onSend={(prompt) => void conversation.send(prompt)}
            onStop={() => void conversation.stop()}
          />
        </>
      )}
    </>
  );
}

function headerTitle(bot: BotLookup, chatTitle: string): string {
  switch (bot.kind) {
    case "found":
      return bot.bot.name;
    case "loading":
      return "";
    case "none":
    case "failed":
      return chatTitle;
  }
}

function waitingCall(items: TimelineItem[], openTurn: number | null): Waiting | null {
  const question = waitingQuestion(items, openTurn);
  if (question !== null) return { kind: "question", item: question };
  const approval = waitingApproval(items, openTurn);
  if (approval !== null) return { kind: "approval", item: approval };
  return null;
}

function WaitingPanel({
  waiting,
  conversationId,
  onAnswered,
  onSkip,
}: {
  waiting: Waiting;
  conversationId: string;
  onAnswered: () => void;
  onSkip: () => void;
}) {
  const props = { item: waiting.item, conversationId, onAnswered, onSkip };
  switch (waiting.kind) {
    case "question":
      return <QuestionPanel {...props} />;
    case "approval":
      return <ApprovalPanel {...props} />;
  }
}

function WaitingBar({ waiting, onUnfold }: { waiting: Waiting; onUnfold: () => void }) {
  switch (waiting.kind) {
    case "question":
      return (
        <QuestionBar
          question={questionOf(waiting.item)?.question ?? "A question"}
          onAnswer={onUnfold}
        />
      );
    case "approval":
      return <ApprovalBar item={waiting.item} onReview={onUnfold} />;
  }
}

"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";

import { waitingApproval } from "@/components/answer/approval";
import { ApprovalBar, ApprovalPanel } from "@/components/answer/ApprovalPanel";
import { handOverOf, waitingHandOver } from "@/components/answer/handOver";
import { HandOverBar, HandOverPanel } from "@/components/answer/HandOverPanel";
import { questionOf, waitingQuestion } from "@/components/answer/question";
import { QuestionBar, QuestionPanel } from "@/components/answer/QuestionPanel";
import { refreshSidebar } from "@/components/chat/Sidebar";
import { type Found, useFound } from "@/components/chat/useFound";
import { ChatHeader } from "@/components/conversation/ChatHeader";
import { Composer } from "@/components/conversation/Composer";
import { QueuedBubble } from "@/components/conversation/Message";
import { Timeline } from "@/components/conversation/Timeline";
import type { Speaker, TimelineItem, ToolItem } from "@/components/conversation/timelineItems";
import { useConversation } from "@/components/conversation/useConversation";
import { useElapsed } from "@/components/conversation/useElapsed";
import { useTimeline } from "@/components/conversation/useTimeline";
import { listBots, listGroups } from "@/lib/api";

type Waiting =
  | { kind: "question"; item: ToolItem }
  | { kind: "hand_over"; item: ToolItem }
  | { kind: "approval"; item: ToolItem };

/** One bot's or one group's chat, under its name. */
export default function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const conversation = useConversation(id);
  const bot = useFound(listBots, id, "Could not load bots.");
  const group = useFound(listGroups, id, "Could not load groups.");
  const { items, openTurn, speakers } = useTimeline(conversation.events);
  const waiting = useMemo(
    () => (conversation.running ? null : waitingCall(items, openTurn)),
    [conversation.running, items, openTurn],
  );
  const elapsed = useElapsed(conversation.running || conversation.sending !== null);
  const [folded, setFolded] = useState<string | null>(null);
  const wasRunning = useRef(false);

  useEffect(() => {
    if (wasRunning.current && !conversation.running) refreshSidebar();
    wasRunning.current = conversation.running;
  }, [conversation.running]);

  const host = speakerOf(bot);

  if (bot.kind === "none" && group.kind === "none") {
    return <p className="px-6 py-6 text-sm text-danger">No bot or group has the id {id}.</p>;
  }

  return (
    <>
      <ChatHeader
        chat={host ?? speakerOf(group)}
        editHref={host === null ? null : `/bots/${id}`}
        elapsed={elapsed}
        canCompact={!conversation.running}
        onCompact={() => void conversation.compact()}
        onClear={() => void conversation.clear()}
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        {conversation.loading ? (
          <p className="px-6 py-6 text-sm text-ink-soft">Loading…</p>
        ) : (
          <>
            <Timeline
              items={items}
              openTurn={openTurn}
              speakers={speakers}
              host={host}
              sending={conversation.sending}
              elapsed={elapsed}
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
            chatId={id}
            running={conversation.running}
            onSend={(prompt, files) => void conversation.send(prompt, files)}
            onStop={() => void conversation.stop()}
          />
        </>
      )}
    </>
  );
}

function speakerOf(found: Found<Speaker>): Speaker | null {
  return found.kind === "found" ? { id: found.item.id, name: found.item.name } : null;
}

function waitingCall(items: TimelineItem[], openTurn: number | null): Waiting | null {
  const question = waitingQuestion(items, openTurn);
  if (question !== null) return { kind: "question", item: question };
  const handOver = waitingHandOver(items, openTurn);
  if (handOver !== null) return { kind: "hand_over", item: handOver };
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
    case "hand_over":
      return (
        <HandOverPanel
          item={waiting.item}
          conversationId={conversationId}
          onAnswered={onAnswered}
          onFold={onSkip}
        />
      );
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
    case "hand_over":
      return (
        <HandOverBar
          step={handOverOf(waiting.item)?.step ?? "A step on the computer"}
          onShow={onUnfold}
        />
      );
    case "approval":
      return <ApprovalBar item={waiting.item} onReview={onUnfold} />;
  }
}

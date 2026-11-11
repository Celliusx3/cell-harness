"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { ApprovalRecord } from "@/components/answer/ApprovalPanel";
import { CLIENT_TOOLS } from "@/components/answer/clientTools";
import { Activity } from "@/components/conversation/Activity";
import { BotBlock } from "@/components/conversation/BotBlock";
import { Compaction } from "@/components/conversation/Compaction";
import {
  AssistantBubble,
  PlainBubble,
  QueuedBubble,
  UserBubble,
} from "@/components/conversation/Message";
import { MODE_ICONS, MODE_LABELS } from "@/components/conversation/ModePicker";
import { ThinkingRow } from "@/components/conversation/ThinkingRow";
import type { Speaker, TimelineItem, ToolItem } from "@/components/conversation/timelineItems";
import type { ApprovalMode } from "@/lib/types";
import { ToolCard } from "@/components/conversation/ToolCard";
import { ReplyUsage } from "@/components/conversation/ReplyUsage";
import { progressOf } from "@/components/conversation/turnProgress";
import { turnRows } from "@/components/conversation/turnRows";
import { turnUsage } from "@/components/conversation/usage";

function scrollParent(node: HTMLElement | null): HTMLElement | null {
  for (let step = node?.parentElement ?? null; step; step = step.parentElement) {
    const overflow = getComputedStyle(step).overflowY;
    if (overflow === "auto" || overflow === "scroll") return step;
  }
  return null;
}

interface ItemProps {
  item: TimelineItem;
  openTurn: number | null;
  conversationId: string;
  onAnswered: () => void;
}

/** Renders timeline items, from the snapshot and the live stream alike. */
export function Timeline({
  items,
  openTurn,
  speakers,
  host,
  sending,
  queued,
  elapsed,
  onAnswered,
}: {
  items: TimelineItem[];
  openTurn: number | null;
  speakers: ReadonlyMap<number, Speaker>;
  host: Speaker | null;
  sending: string | null;
  queued: string[];
  elapsed: string | null;
  onAnswered: () => void;
}) {
  const floor = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const { id: conversationId } = useParams<{ id: string }>();

  useEffect(() => {
    const scroller = scrollParent(floor.current);
    if (!scroller) return;
    const onScroll = () => {
      const slack =
        scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
      pinned.current = slack < 80;
    };
    scroller.addEventListener("scroll", onScroll, { passive: true });
    return () => scroller.removeEventListener("scroll", onScroll);
  }, []);

  const stays = (item: ToolItem) =>
    item.call.name in CLIENT_TOOLS ||
    item.ui !== null ||
    item.files.length > 0 ||
    (item.result === null && openTurn === null);
  const shared = { openTurn, conversationId, onAnswered };
  const rows = turnRows(items, { speakers, stays });
  const progress = progressOf(rows, items, openTurn, sending);
  const isStarting = progress?.kind === "starting";
  const openTurnSpeaker = (openTurn === null ? undefined : speakers.get(openTurn)) ?? host;

  useEffect(() => {
    if (pinned.current) floor.current?.scrollIntoView({ block: "end" });
  }, [items, sending, isStarting, queued]);

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6">
      {rows.map((row) => {
        if (row.kind === "item") return <Item key={row.item.key} item={row.item} {...shared} />;
        return (
          <ReplyUsage key={row.key} usage={row.turn === openTurn ? null : usageOf(items, row.turn)}>
            <BotBlock speaker={row.speaker ?? host}>
              {row.parts.map((part) =>
                part.kind === "item" ? (
                  <Item key={part.item.key} item={part.item} {...shared} />
                ) : (
                  <Activity
                    key={part.key}
                    progress={part.turn === openTurn ? progress : null}
                    tools={part.items.filter((item) => item.kind === "tool").length}
                    failed={
                      part.items.filter((item) => item.kind === "tool" && item.error !== null).length
                    }
                  >
                    {part.items.map((item) => (
                      <Item key={item.key} item={item} {...shared} />
                    ))}
                  </Activity>
                ),
              )}
            </BotBlock>
          </ReplyUsage>
        );
      })}
      {sending !== null && <PlainBubble content={sending} />}
      {isStarting && <ThinkingRow speaker={openTurnSpeaker} elapsed={elapsed} />}
      {queued.map((text, index) => (
        <QueuedBubble key={index} content={text} />
      ))}
      <div ref={floor} />
    </div>
  );
}

function usageOf(items: TimelineItem[], turn: number) {
  return turnUsage(
    items.flatMap((item) => (item.kind === "assistant" && item.turn === turn ? [item.usage] : [])),
  );
}

function Item({ item, openTurn, conversationId, onAnswered }: ItemProps) {
  switch (item.kind) {
    case "user":
      return <UserBubble item={item} chatId={conversationId} />;
    case "assistant":
      return <AssistantBubble item={item} />;
    case "tool": {
      const Handler = CLIENT_TOOLS[item.call.name];
      if (Handler)
        return <Handler item={item} conversationId={conversationId} onAnswered={onAnswered} />;
      if (item.result === null && openTurn === null) return <ApprovalRecord item={item} />;
      return <ToolCard item={item} />;
    }
    case "notice":
      return (
        <p className={`text-xs ${item.tone === "error" ? "text-danger" : "text-ink-soft"}`}>
          {item.text}
        </p>
      );
    case "compaction":
      return <Compaction item={item} />;
    case "instructions":
      return <p className="text-center text-xs text-ink-soft">Instructions updated</p>;
    case "mode":
      return (
        <ModeLine mode={item.mode} />
      );
  }
}

/** One switch of the chat's mode, as a divider with the mode's icon. */
function ModeLine({ mode }: { mode: ApprovalMode }) {
  const Icon = MODE_ICONS[mode];
  return (
    <div className="flex items-center gap-3 text-xs text-ink-soft">
      <span aria-hidden className="h-px flex-1 bg-line" />
      <span className={`flex items-center gap-1.5 ${mode === "auto" ? "text-accent" : ""}`}>
        <Icon size={13} />
        Switched to {MODE_LABELS[mode]}
      </span>
      <span aria-hidden className="h-px flex-1 bg-line" />
    </div>
  );
}

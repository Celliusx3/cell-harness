"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { ApprovalRecord } from "@/components/answer/ApprovalPanel";
import { CLIENT_TOOLS } from "@/components/answer/clientTools";
import { Activity } from "@/components/conversation/Activity";
import { BotBlock } from "@/components/conversation/BotAvatar";
import { Compaction } from "@/components/conversation/Compaction";
import { AssistantBubble, PlainBubble, UserBubble } from "@/components/conversation/Message";
import { ThinkingRow } from "@/components/conversation/ThinkingRow";
import type { Speaker, TimelineItem, ToolItem } from "@/components/conversation/timelineItems";
import { ToolCard } from "@/components/conversation/ToolCard";
import { progressOf } from "@/components/conversation/turnProgress";
import { turnRows } from "@/components/conversation/turnRows";

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
  onAnswered,
}: {
  items: TimelineItem[];
  openTurn: number | null;
  speakers: ReadonlyMap<number, Speaker>;
  host: Speaker | null;
  sending: string | null;
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
  const isThinking = progressOf(rows, openTurn, sending)?.kind === "thinking";
  const thinker = (openTurn === null ? undefined : speakers.get(openTurn)) ?? host;

  useEffect(() => {
    if (pinned.current) floor.current?.scrollIntoView({ block: "end" });
  }, [items, sending, isThinking]);

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6">
      {rows.map((row) => {
        if (row.kind === "item") return <Item key={row.item.key} item={row.item} {...shared} />;
        return (
          <BotBlock key={row.key} speaker={row.speaker ?? host}>
            {row.parts.map((part) =>
              part.kind === "item" ? (
                <Item key={part.item.key} item={part.item} {...shared} />
              ) : (
                <Activity
                  key={part.key}
                  live={part.turn === openTurn}
                  tools={part.items.filter((item) => item.kind === "tool").length}
                >
                  {part.items.map((item) => (
                    <Item key={item.key} item={item} {...shared} />
                  ))}
                </Activity>
              ),
            )}
          </BotBlock>
        );
      })}
      {sending !== null && <PlainBubble content={sending} />}
      {isThinking && <ThinkingRow speaker={thinker} />}
      <div ref={floor} />
    </div>
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
  }
}

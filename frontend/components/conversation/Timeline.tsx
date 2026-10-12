"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { ApprovalRecord } from "@/components/answer/ApprovalPanel";
import { CLIENT_TOOLS } from "@/components/answer/clientTools";
import { Activity } from "@/components/conversation/Activity";
import { BotAvatar } from "@/components/conversation/BotAvatar";
import { Compaction } from "@/components/conversation/Compaction";
import { AssistantBubble, UserBubble } from "@/components/conversation/Message";
import type { Speaker, TimelineItem, ToolItem } from "@/components/conversation/timelineItems";
import { ToolCard } from "@/components/conversation/ToolCard";
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
  onAnswered,
}: {
  items: TimelineItem[];
  openTurn: number | null;
  speakers: ReadonlyMap<number, Speaker>;
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

  useEffect(() => {
    if (pinned.current) floor.current?.scrollIntoView({ block: "end" });
  }, [items]);

  const stays = (item: ToolItem) =>
    item.call.name in CLIENT_TOOLS ||
    item.ui !== null ||
    (item.result === null && openTurn === null);
  const shared = { openTurn, conversationId, onAnswered };

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6">
      {turnRows(items, { speakers, stays }).map((row) => {
        if (row.kind === "item") return <Item key={row.item.key} item={row.item} {...shared} />;
        const parts = (
          <div className="min-w-0 flex-1 space-y-3">
            {row.speaker !== null && (
              <p className="text-sm font-semibold leading-7 text-ink">{row.speaker.name}</p>
            )}
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
          </div>
        );
        if (row.speaker === null) return <div key={row.key}>{parts}</div>;
        return (
          <div key={row.key} className="flex gap-3">
            <BotAvatar speaker={row.speaker} />
            {parts}
          </div>
        );
      })}
      <div ref={floor} />
    </div>
  );
}

function Item({ item, openTurn, conversationId, onAnswered }: ItemProps) {
  switch (item.kind) {
    case "user":
      return <UserBubble item={item} />;
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

"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { ApprovalRecord } from "@/components/answer/ApprovalPanel";
import { TicketQuestionPanel } from "@/components/answer/TicketQuestionPanel";
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
import { ScheduleChangeLine } from "@/components/conversation/ScheduleChangeLine";
import { ScheduledBubble } from "@/components/conversation/ScheduledBubble";
import { ThinkingRow } from "@/components/conversation/ThinkingRow";
import { acceptedTickets, TicketLines } from "@/components/conversation/TicketLines";
import { ticketReports, type TicketReports } from "@/components/conversation/ticketReports";
import type { Speaker, TimelineItem, ToolItem } from "@/components/conversation/timelineItems";
import type { FileSource } from "@/lib/api";
import type { ApprovalMode } from "@/lib/types";
import { ToolCard } from "@/components/conversation/ToolCard";
import { progressOf } from "@/components/conversation/turnProgress";
import { turnRows } from "@/components/conversation/turnRows";

const TICKET_ROUTE = "ticket_route";

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
  source: FileSource;
  onAnswered: () => void;
  reports: ReadonlyMap<string, TicketReports>;
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
  source,
}: {
  items: TimelineItem[];
  openTurn: number | null;
  speakers: ReadonlyMap<number, Speaker>;
  host: Speaker | null;
  sending: string | null;
  queued: string[];
  elapsed: string | null;
  onAnswered: () => void;
  source: FileSource;
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
    const keepPinned = new ResizeObserver(() => {
      if (pinned.current) floor.current?.scrollIntoView({ block: "end" });
    });
    keepPinned.observe(scroller);
    scroller.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      keepPinned.disconnect();
      scroller.removeEventListener("scroll", onScroll);
    };
  }, []);

  const stays = (item: ToolItem) =>
    item.call.name in CLIENT_TOOLS ||
    (item.call.name === TICKET_ROUTE && acceptedTickets(item).length > 0) ||
    item.ui !== null ||
    item.files.length > 0 ||
    (item.result === null && openTurn === null);
  const shared = { openTurn, conversationId, source, onAnswered, reports: ticketReports(items) };
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
          <BotBlock key={row.key} speaker={row.speaker ?? host} continues={row.continues}>
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

function Item({ item, openTurn, conversationId, source, onAnswered, reports }: ItemProps) {
  switch (item.kind) {
    case "user":
      return <UserBubble item={item} source={source} />;
    case "scheduled":
      return <ScheduledBubble item={item} />;
    case "assistant":
      return <AssistantBubble item={item} />;
    case "tool": {
      const Handler = CLIENT_TOOLS[item.call.name];
      if (Handler)
        return <Handler item={item} conversationId={conversationId} onAnswered={onAnswered} />;
      if (item.result === null && openTurn === null) return <ApprovalRecord item={item} />;
      if (item.call.name === TICKET_ROUTE && acceptedTickets(item).length > 0)
        return <TicketLines item={item} chatId={conversationId} reports={reports} />;
      return <ToolCard item={item} source={source} />;
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
    case "scheduleChange":
      return <ScheduleChangeLine change={item.change} />;
    case "ticketQuestion":
      return <TicketQuestionPanel item={item} />;
    case "ticketResult":
      return null;
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

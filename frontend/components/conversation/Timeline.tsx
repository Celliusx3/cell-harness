"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { ApprovalRequest } from "@/components/answer/ApprovalRequest";
import { CLIENT_TOOLS } from "@/components/answer/clientTools";
import { Compaction } from "@/components/conversation/Compaction";
import { AssistantBubble, UserBubble } from "@/components/conversation/Message";
import type { TimelineItem } from "@/components/conversation/timelineItems";
import { ToolCard } from "@/components/conversation/ToolCard";

/** Renders timeline items, from the snapshot and the live stream alike. */
export function Timeline({
  items,
  openTurn,
  onAnswered,
}: {
  items: TimelineItem[];
  openTurn: number | null;
  onAnswered: () => void;
}) {
  const floor = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const { id: conversationId } = useParams<{ id: string }>();

  useEffect(() => {
    const scroller = floor.current?.parentElement;
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

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6">
      {items.map((item) => {
        switch (item.kind) {
          case "user":
            return <UserBubble key={item.key} item={item} />;
          case "assistant":
            return item.content ? (
              <AssistantBubble key={item.key} item={item} />
            ) : null;
          case "tool": {
            const Handler = CLIENT_TOOLS[item.call.name];
            if (Handler)
              return (
                <Handler
                  key={item.key}
                  item={item}
                  conversationId={conversationId}
                  onAnswered={onAnswered}
                />
              );
            if (item.result === null && openTurn === null)
              return (
                <ApprovalRequest
                  key={item.key}
                  item={item}
                  conversationId={conversationId}
                  onAnswered={onAnswered}
                />
              );
            return <ToolCard key={item.key} item={item} />;
          }
          case "notice":
            return (
              <p
                key={item.key}
                className={`text-xs ${item.tone === "error" ? "text-danger" : "text-ink-soft"}`}
              >
                {item.text}
              </p>
            );
          case "compaction":
            return <Compaction key={item.key} item={item} />;
        }
      })}
      <div ref={floor} />
    </div>
  );
}

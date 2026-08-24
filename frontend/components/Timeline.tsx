"use client";

import { useEffect, useRef } from "react";

import { AssistantBubble, UserBubble } from "@/components/Message";
import { ToolCard } from "@/components/ToolCard";
import type { TimelineItem } from "@/lib/timeline";

/**
 * **The one renderer.**
 *
 * It takes timeline items and has no idea whether the events behind them came
 * from the snapshot or the live stream. That is what makes "a reloaded
 * conversation renders identically to the live stream" true by construction
 * rather than by keeping two components in step.
 */
export function Timeline({ items }: { items: TimelineItem[] }) {
  const floor = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);

  // Follow the stream only while the user is already at the bottom. Scrolling up
  // to re-read something during a long reply must not be yanked back.
  useEffect(() => {
    const scroller = floor.current?.parentElement;
    if (!scroller) return;
    const onScroll = () => {
      const slack = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
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
            // A step that went straight to tool calls has no prose. Skipped
            // here rather than dropped in the reducer, which still needs the
            // item so `usage` and `interrupted` are not lost.
            return item.content ? <AssistantBubble key={item.key} item={item} /> : null;
          case "tool":
            return <ToolCard key={item.key} item={item} />;
          case "notice":
            return (
              <p
                key={item.key}
                className={`text-xs ${item.tone === "error" ? "text-danger" : "text-ink-soft"}`}
              >
                {item.text}
              </p>
            );
        }
      })}
      <div ref={floor} />
    </div>
  );
}

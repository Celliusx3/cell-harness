"use client";

import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { AssistantItem, UserItem } from "@/lib/timeline";

export function UserBubble({ item }: { item: UserItem }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] whitespace-pre-wrap break-words rounded-2xl bg-accent px-4 py-2.5 text-sm text-white">
        {item.content}
      </div>
    </div>
  );
}

export function AssistantBubble({ item }: { item: AssistantItem }) {
  return (
    <div className="flex flex-col gap-1">
      <div
        className={`prose prose-sm max-w-none prose-pre:bg-surface-sunken prose-pre:text-ink ${
          item.streaming ? "caret" : ""
        }`}
      >
        {/* Markdown, but no syntax highlighting: Shiki or Prism is real weight
            for a phase whose only tool is a clock. */}
        <Markdown remarkPlugins={[remarkGfm]}>{item.content}</Markdown>
      </div>
      {item.interrupted && (
        <p className="text-xs italic text-ink-soft">
          Stopped part-way — this is the text that had arrived.
        </p>
      )}
    </div>
  );
}

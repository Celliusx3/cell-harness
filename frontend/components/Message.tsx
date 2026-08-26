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

/**
 * A message the server is holding until the current turn finishes.
 *
 * Muted and labelled, because it is genuinely in a different state from the rest
 * of the conversation: it has been accepted but the model has not seen it, and it
 * is not in the session log yet. Drawing it identically to a sent message would
 * claim more than is true.
 */
export function QueuedBubble({ content }: { content: string }) {
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="max-w-[80%] whitespace-pre-wrap break-words rounded-2xl bg-accent/40 px-4 py-2.5 text-sm text-white">
        {content}
      </div>
      <span className="text-xs text-ink-soft">queued — answered next</span>
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

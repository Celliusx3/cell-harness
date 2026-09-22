"use client";

import type { Element } from "hast";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { useState } from "react";

import { CodeBlock } from "@/components/conversation/CodeBlock";
import type { Invocation } from "@/components/conversation/invocation";
import type { AssistantItem, UserItem } from "@/components/conversation/timelineItems";

export function UserBubble({ item }: { item: UserItem }) {
  if (item.invoked) return <InvokedBubble item={item} invoked={item.invoked} />;
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] whitespace-pre-wrap break-words rounded-2xl bg-accent px-4 py-2.5 text-sm text-white">
        {item.content}
      </div>
    </div>
  );
}

/** A `/name` message: the typed line, with the skill it loaded as a chip. */
function InvokedBubble({ item, invoked }: { item: UserItem; invoked: Invocation }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="max-w-[80%] whitespace-pre-wrap break-words rounded-2xl bg-accent px-4 py-2.5 text-sm text-white">
        {invoked.typed}
      </div>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        title={open ? "Hide what was sent" : "Show what was sent"}
        className="rounded-md border border-line bg-surface px-1.5 py-0.5 font-mono text-xs text-ink-soft transition hover:text-ink"
      >
        {invoked.skill}
      </button>
      {open ? (
        <pre className="max-h-96 w-full max-w-[80%] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-surface-sunken p-2 font-mono text-xs">
          {item.content}
        </pre>
      ) : null}
    </div>
  );
}

/** A message the server is holding until the current turn finishes. */
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

/** A fenced block, read off the hast node markdown hands the `pre` override. */
function fenced(node: Element | undefined): { code: string; language: string } | null {
  const child = node?.children[0];
  if (child?.type !== "element" || child.tagName !== "code") return null;
  const names = child.properties?.className;
  const tag = Array.isArray(names)
    ? names.map(String).find((name) => name.startsWith("language-"))
    : undefined;
  const text = child.children[0];
  if (tag === undefined || text?.type !== "text") return null;
  // remark leaves exactly one trailing newline on a fence; `.trim()` would eat indentation.
  return { code: text.value.replace(/\n$/, ""), language: tag.slice("language-".length) };
}

/** Module-level so its identity is stable across the re-render every stream chunk causes. */
const MARKDOWN: Components = {
  pre({ node, children }) {
    const block = fenced(node);
    if (block === null) return <pre>{children}</pre>;
    return (
      <div className="not-prose my-4">
        <CodeBlock code={block.code} language={block.language} className="bg-surface-sunken" />
      </div>
    );
  },
};

export function AssistantBubble({ item }: { item: AssistantItem }) {
  return (
    <div className="flex flex-col gap-1">
      <div
        className={`prose prose-sm max-w-none prose-pre:bg-surface-sunken prose-pre:text-ink ${
          item.streaming ? "caret" : ""
        }`}
      >
        <Markdown remarkPlugins={[remarkGfm]} components={MARKDOWN}>
          {item.content}
        </Markdown>
      </div>
      {item.interrupted && (
        <p className="text-xs italic text-ink-soft">
          Stopped part-way — this is the text that had arrived.
        </p>
      )}
    </div>
  );
}

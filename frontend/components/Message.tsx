"use client";

import type { Element } from "hast";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { CodeBlock } from "@/components/CodeBlock";
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

/**
 * A fenced block, read off the hast node markdown hands the `pre` override.
 *
 * Returns null for a fence with no language, which then renders as an ordinary
 * `<pre>` — highlighting a stack trace as TypeScript is worse than not trying.
 */
function fenced(node: Element | undefined): { code: string; language: string } | null {
  const child = node?.children[0];
  if (child?.type !== "element" || child.tagName !== "code") return null;
  const names = child.properties?.className;
  const tag = Array.isArray(names)
    ? names.map(String).find((name) => name.startsWith("language-"))
    : undefined;
  const text = child.children[0];
  if (tag === undefined || text?.type !== "text") return null;
  // Markdown appends exactly one newline to a fence. `.trim()` would also eat
  // the first line's indentation, which for a program is content.
  return { code: text.value.replace(/\n$/, ""), language: tag.slice("language-".length) };
}

/**
 * Module-level so its identity is stable across the re-render every stream chunk
 * causes.
 *
 * `pre` is overridden and `code` deliberately is not: an untagged fence and
 * inline code reach the `code` component as the same shape, so discriminating
 * there renders ``` blocks as inline text — whitespace collapsed, bolded, and
 * wrapped in literal backticks by the typography plugin. Only a fence is ever a
 * `pre`, so this override cannot catch the wrong thing.
 *
 * The weight is worth it now in a way it was not when the only tool was a clock:
 * in code mode the model writes TypeScript in most replies.
 */
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

"use client";

import { ChevronRight, TriangleAlert, Wrench } from "lucide-react";
import { useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import type { ToolItem } from "@/lib/timeline";
import type { ContentBlock } from "@/lib/types";

/** Code mode's runner. Its `code` field is a program; its siblings are prose. */
const EXECUTE = "execute_typescript";

/**
 * One tool call, collapsed to a line until asked to open.
 *
 * Rendered entirely from `tool/call` and `tool/result` — the name, the model's
 * raw argument string, and the already-rendered result. A tool has no way to
 * attach richer display data yet; that field arrives in phase 5, with the first
 * MCP tool that returns something worth drawing.
 */
export function ToolCard({ item }: { item: ToolItem }) {
  const [open, setOpen] = useState(false);
  const failed = item.error !== null;
  const pending = item.result === null;

  return (
    <div
      className={`overflow-hidden rounded-xl border text-sm ${
        failed ? "border-danger/40 bg-danger-soft" : "border-line bg-surface-sunken"
      }`}
    >
      <button
        onClick={() => setOpen((was) => !was)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        <ChevronRight
          size={14}
          className={`shrink-0 text-ink-soft transition-transform ${open ? "rotate-90" : ""}`}
        />
        {failed ? (
          <TriangleAlert size={14} className="shrink-0 text-danger" />
        ) : (
          <Wrench size={14} className="shrink-0 text-ink-soft" />
        )}
        <span className="font-mono text-xs font-medium">{item.call.name}</span>
        <span className="ml-auto shrink-0 text-xs text-ink-soft">
          {pending ? "running…" : failed ? item.error : "done"}
        </span>
      </button>

      {open && (
        <div className="space-y-2 border-t border-line px-3 py-2">
          <Arguments raw={item.call.arguments} tool={item.call.name} />
          {/* Deliberately shown whole. A tool result is exactly what the model
              was given, and a truncated one would misrepresent the turn. */}
          {item.result !== null && <Result blocks={item.result} />}
        </div>
      )}
    </div>
  );
}

/**
 * The model's argument string, one block per field.
 *
 * It arrives as JSON on a single line, so code mode — whose whole argument *is*
 * a program — renders as `"let i = 0;\nconst results…"`. Splitting the object
 * lets each string value print as itself, which is what turns an escaped script
 * back into readable source.
 *
 * Anything that is not a JSON object falls back to the raw string, because a
 * malformed argument string is exactly when you need to see what was really
 * sent.
 */
function Arguments({ raw, tool }: { raw: string; tool: string }) {
  const fields = parseFields(raw);
  if (fields === null) return <Block label="Arguments" body={raw} />;
  return (
    <>
      {fields.map(([name, body]) => (
        // Gated on the tool as well as the field name: `Arguments` splits any
        // JSON object, so an MCP tool that happens to take a `code` argument
        // would otherwise be highlighted as TypeScript.
        <Block key={name} label={name} body={body} script={tool === EXECUTE && name === "code"} />
      ))}
    </>
  );
}

function parseFields(raw: string): [string, string][] | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) return null;
  const entries = Object.entries(parsed);
  if (entries.length === 0) return null;
  // Strings print as themselves so newlines survive; everything else is shaped
  // by the same indented JSON the model's own tool results use.
  return entries.map(([name, value]) => [
    name,
    typeof value === "string" ? value : JSON.stringify(value, null, 2),
  ]);
}

/**
 * A result's blocks: the prose as one block, and each `tool_reference` as a
 * chip — the tool is in the model's list from the next request on, and the
 * card is where a person sees that happen.
 */
function Result({ blocks }: { blocks: ContentBlock[] }) {
  const text = blocks
    .filter((b): b is Extract<ContentBlock, { type: "text" }> => b.type === "text")
    .map((b) => b.text)
    .join("\n\n");
  const referenced = blocks
    .filter((b): b is Extract<ContentBlock, { type: "tool_reference" }> => b.type === "tool_reference")
    .map((b) => b.tool_name);
  return (
    <>
      {text !== "" && <Block label="Result" body={text} />}
      {referenced.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-ink-soft">
            Now callable
          </p>
          <div className="flex flex-wrap gap-1">
            {referenced.map((name) => (
              <span
                key={name}
                className="rounded-md border border-line bg-surface px-1.5 py-0.5 font-mono text-xs"
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function Block({ label, body, script = false }: { label: string; body: string; script?: boolean }) {
  return (
    <div>
      <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-ink-soft">{label}</p>
      {/* Capped and scrolled rather than truncated: a 200-line script would
          otherwise push the rest of the conversation off screen, and cutting it
          short would hide the line you opened the card to read. */}
      {script ? (
        <CodeBlock code={body} language="tsx" className="bg-surface" />
      ) : (
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-surface p-2 font-mono text-xs">
          {body}
        </pre>
      )}
    </div>
  );
}

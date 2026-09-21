"use client";

import { ChevronRight, ExternalLink, TriangleAlert, Wrench } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import type { ToolItem } from "@/lib/timeline";
import type { ContentBlock } from "@/lib/types";

/** The argument field of each tool that is shown as a program. */
const SCRIPT_FIELDS: Record<string, string> = { execute_typescript: "code" };

/** One tool call, collapsed to a line until asked to open. */
export function ToolCard({ item }: { item: ToolItem }) {
  const [open, setOpen] = useState(false);
  const { id: conversationId } = useParams<{ id: string }>();
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

      {item.ui !== null && (
        <div className="border-t border-line px-3 py-2">
          <Link
            href={`/apps/${encodeURIComponent(conversationId)}/${encodeURIComponent(item.call.id)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1 text-xs font-medium hover:bg-accent-soft"
          >
            <ExternalLink size={13} />
            Open app
          </Link>
        </div>
      )}

      {open && (
        <div className="space-y-2 border-t border-line px-3 py-2">
          <Arguments raw={item.call.arguments} tool={item.call.name} />
          {item.result !== null && <Result blocks={item.result} />}
        </div>
      )}
    </div>
  );
}

/** The model's argument string, one block per field. */
export function Arguments({ raw, tool }: { raw: string; tool: string }) {
  const fields = parseFields(raw);
  if (fields === null) return <Block label="Arguments" body={raw} />;
  return (
    <>
      {fields.map(([name, body]) => (
        <Block key={name} label={name} body={body} script={SCRIPT_FIELDS[tool] === name} />
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
  return entries.map(([name, value]) => [
    name,
    typeof value === "string" ? value : JSON.stringify(value, null, 2),
  ]);
}

/** A result's blocks: the prose as one block, and each `tool_reference` as a chip */
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

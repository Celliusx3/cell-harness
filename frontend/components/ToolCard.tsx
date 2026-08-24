"use client";

import { ChevronRight, TriangleAlert, Wrench } from "lucide-react";
import { useState } from "react";

import type { ToolItem } from "@/lib/timeline";

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
          <Block label="Arguments" body={item.call.arguments} />
          {/* Deliberately shown whole. A tool result is exactly what the model
              was given, and a truncated one would misrepresent the turn. */}
          {item.result !== null && <Block label="Result" body={item.result} />}
        </div>
      )}
    </div>
  );
}

function Block({ label, body }: { label: string; body: string }) {
  return (
    <div>
      <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-ink-soft">{label}</p>
      <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-surface p-2 font-mono text-xs">
        {body}
      </pre>
    </div>
  );
}

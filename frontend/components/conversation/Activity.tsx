"use client";

import { LoaderCircle } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { Progress } from "@/components/conversation/turnProgress";
import {
  TraceCollapsible,
  TraceCollapsibleContent,
  TraceCollapsibleTrigger,
  TraceDescription,
  TraceIcon,
  TraceLine,
  TraceTitle,
} from "@/components/ui/trace";

/** A turn's tool calls and in-between notes behind one line: open while it works, folded after. */
export function Activity({
  progress,
  tools,
  failed,
  children,
}: {
  progress: Progress | null;
  tools: number;
  failed: number;
  children: ReactNode;
}) {
  const [chosen, setChosen] = useState<boolean | null>(null);
  const title = liveTitle(progress);
  return (
    <TraceCollapsible open={chosen ?? title !== null} onOpenChange={setChosen}>
      <TraceCollapsibleTrigger>
        {title === null ? (
          <FoldedLine tools={tools} failed={failed} />
        ) : (
          <LiveLine title={title} tools={tools} />
        )}
      </TraceCollapsibleTrigger>
      <TraceCollapsibleContent className="space-y-3 border-line pl-3 text-ink">
        {children}
      </TraceCollapsibleContent>
    </TraceCollapsible>
  );
}

function liveTitle(progress: Progress | null): string | null {
  if (progress === null) return null;
  switch (progress.kind) {
    case "running":
      return `Running ${progress.tool}`;
    case "thinking":
      return "Thinking";
    case "starting":
    case "writing":
      return null;
    default: {
      const _exhaustive: never = progress;
      return _exhaustive;
    }
  }
}

function LiveLine({ title, tools }: { title: string; tools: number }) {
  return (
    <TraceLine status="running">
      <TraceIcon>
        <LoaderCircle className="animate-spin text-accent motion-reduce:animate-none" />
      </TraceIcon>
      <TraceTitle>{title}</TraceTitle>
      {tools > 0 && <TraceDescription>· {toolCount(tools)}</TraceDescription>}
    </TraceLine>
  );
}

function FoldedLine({ tools, failed }: { tools: number; failed: number }) {
  return (
    <TraceLine>
      <TraceTitle>{tools > 0 ? `Used ${toolCount(tools)}` : "Show steps"}</TraceTitle>
      {failed > 0 && <TraceDescription className="text-danger">· {failed} failed</TraceDescription>}
    </TraceLine>
  );
}

function toolCount(tools: number): string {
  return `${tools} ${tools === 1 ? "tool" : "tools"}`;
}

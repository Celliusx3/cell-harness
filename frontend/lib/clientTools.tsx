"use client";

import type { ComponentType } from "react";
import { useRef, useState } from "react";

import { LocationRequest } from "@/components/LocationRequest";
import { sendToolOutput } from "@/lib/api";
import type { ToolItem } from "@/lib/timeline";
import type { ClientOutput } from "@/lib/types";

/** What a client-tool handler is given: the call, where it lives, and what
 *  to do once the output is posted — wake the stream, since the answer opened
 *  a new turn. */
export interface ClientToolProps {
  item: ToolItem;
  conversationId: string;
  onAnswered: () => void;
}

/**
 * **The handler map** — Vercel's `onToolCall`, as a lookup by tool name.
 *
 * A tool declared on the server as a client tool is answered by whichever
 * component is named here; the timeline and the `/answer` page dispatch by
 * this map and know nothing else. A new datum is one entry. A client tool
 * with no entry falls back to the plain tool card, which shows it pending
 * until the person types something and the server skips it.
 */
export const CLIENT_TOOLS: Record<string, ComponentType<ClientToolProps>> = {
  get_location: LocationRequest,
};

export type Phase = "asking" | "working" | "sent";

/**
 * What every handler needs and none should own: whether the call is still
 * pending, the phase this page is in, and `send` — which posts the output,
 * wakes the stream for the turn that output opened, and swallows the two
 * "nothing to do" answers. `decided` guards a handler's automatic path
 * against React re-running an effect: one answer per mount.
 */
export function useClientTool<T>({
  item,
  conversationId,
  onAnswered,
}: ClientToolProps) {
  const pending = item.result === null;
  const [phase, setPhase] = useState<Phase>("asking");
  const decided = useRef(false);

  const send = async (output: ClientOutput<T>) => {
    decided.current = true;
    setPhase("sent");
    try {
      await sendToolOutput(conversationId, item.call.id, output);
      onAnswered();
    } catch {
      // 404 (no longer pending) or 409 (a turn is running — another tab, or
      // the person typed). The stream will say which; nothing to add here.
    }
  };

  return { pending, phase, setPhase, decided, send };
}

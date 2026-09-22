"use client";

import { useRef, useState } from "react";

import type { ToolItem } from "@/components/conversation/timelineItems";
import { ApiError, sendToolOutput } from "@/lib/api";
import type { ClientOutput, Decision } from "@/lib/types";

/** What a client-tool handler is given: the call, where it lives, and what to do once the output is posted */
export interface ClientToolProps {
  item: ToolItem;
  conversationId: string;
  onAnswered: () => void;
}

export type Phase = "asking" | "working" | "sent";

/** What every handler needs and none should own: whether the call is still pending, the phase this page is in, and `send` */
export function useClientTool<T>({
  item,
  conversationId,
  onAnswered,
}: ClientToolProps) {
  const pending = item.result === null;
  const [phase, setPhase] = useState<Phase>("asking");
  const decided = useRef(false);

  const send = async (output: ClientOutput<T> | Decision) => {
    decided.current = true;
    setPhase("sent");
    try {
      await sendToolOutput(conversationId, item.call.id, output);
      onAnswered();
    } catch (err) {
      const alreadySettled = err instanceof ApiError && (err.status === 404 || err.status === 409);
      if (!alreadySettled) throw err;
    }
  };

  return { pending, phase, setPhase, decided, send };
}

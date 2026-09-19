"use client";

import type { ComponentType } from "react";
import { useRef, useState } from "react";

import { LocationRequest } from "@/components/LocationRequest";
import { ApiError, sendToolOutput } from "@/lib/api";
import type { ToolItem } from "@/lib/timeline";
import type { ClientOutput } from "@/lib/types";

/** What a client-tool handler is given: the call, where it lives, and what to do once the output is posted */
export interface ClientToolProps {
  item: ToolItem;
  conversationId: string;
  onAnswered: () => void;
}

/** The handler component for each client tool. */
export const CLIENT_TOOLS: Record<string, ComponentType<ClientToolProps>> = {
  get_location: LocationRequest,
};

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

  const send = async (output: ClientOutput<T>) => {
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

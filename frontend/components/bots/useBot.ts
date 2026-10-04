"use client";

import { useEffect, useState } from "react";

import { ApiError, listBots } from "@/lib/api";
import type { Bot } from "@/lib/types";

export type BotLookup =
  | { kind: "loading" }
  | { kind: "found"; bot: Bot }
  | { kind: "none" }
  | { kind: "failed"; message: string };

function botLookup(bots: Bot[], id: string): BotLookup {
  const bot = bots.find((candidate) => candidate.id === id);
  return bot === undefined ? { kind: "none" } : { kind: "found", bot };
}

export function useBot(id: string): BotLookup {
  const [lookup, setLookup] = useState<BotLookup>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setLookup({ kind: "loading" });
    listBots()
      .then((bots) => {
        if (!cancelled) setLookup(botLookup(bots, id));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setLookup({
          kind: "failed",
          message: err instanceof ApiError ? err.message : "Could not load bots.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return lookup;
}

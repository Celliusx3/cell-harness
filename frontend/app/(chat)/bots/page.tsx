"use client";

import { useCallback, useEffect, useState } from "react";

import { ArchivedBots } from "@/components/bots/ArchivedBots";
import { BotList } from "@/components/bots/BotList";
import { refreshSidebar } from "@/components/chat/Sidebar";
import { ApiError, listArchivedBots, listBots, listGroups } from "@/lib/api";
import type { Bot, Group } from "@/lib/types";

type Catalog =
  | { kind: "loading" }
  | { kind: "failed"; message: string }
  | { kind: "loaded"; bots: Bot[]; groups: Group[]; archived: Bot[] };

/** Every bot and group, then the archived bots. */
export default function BotsPage() {
  const [catalog, setCatalog] = useState<Catalog>({ kind: "loading" });

  const load = useCallback(async () => {
    try {
      const [bots, groups, archived] = await Promise.all([listBots(), listGroups(), listArchivedBots()]);
      setCatalog({ kind: "loaded", bots, groups, archived });
    } catch (err: unknown) {
      setCatalog({ kind: "failed", message: err instanceof ApiError ? err.message : "Could not load bots." });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function changed() {
    refreshSidebar();
    void load();
  }

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <h1 className="min-w-0 truncate text-sm font-medium">Bots</h1>
      </header>
      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-4">
        {catalog.kind === "loading" && <p className="text-sm text-ink-soft">Loading…</p>}
        {catalog.kind === "failed" && <p className="text-sm text-danger">{catalog.message}</p>}
        {catalog.kind === "loaded" && (
          <>
            <BotList bots={catalog.bots} groups={catalog.groups} archived={catalog.archived} />
            {catalog.archived.length > 0 && <ArchivedBots bots={catalog.archived} onChange={changed} />}
          </>
        )}
      </div>
    </>
  );
}

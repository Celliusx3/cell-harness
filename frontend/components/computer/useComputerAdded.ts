"use client";

import { useEffect, useState } from "react";

import { SERVER } from "@/components/computer/server";
import { listServers } from "@/lib/api";

export type Added = "checking" | "yes" | "no";

/** Whether the `computer` server is added; a failed check counts as added, so the screen says why. */
export function useComputerAdded(): Added {
  const [added, setAdded] = useState<Added>("checking");

  useEffect(() => {
    let cancelled = false;
    listServers()
      .then(({ servers }) => {
        if (!cancelled) setAdded(servers.includes(SERVER) ? "yes" : "no");
      })
      .catch(() => {
        if (!cancelled) setAdded("yes");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return added;
}

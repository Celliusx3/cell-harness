"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api";

export type Found<T> =
  | { kind: "loading" }
  | { kind: "found"; item: T }
  | { kind: "none" }
  | { kind: "failed"; message: string };

function foundIn<T extends { id: string }>(items: T[], id: string): Found<T> {
  const item = items.find((candidate) => candidate.id === id);
  return item === undefined ? { kind: "none" } : { kind: "found", item };
}

export function useFound<T extends { id: string }>(
  load: () => Promise<T[]>,
  id: string,
  failure: string,
): Found<T> {
  const [found, setFound] = useState<Found<T>>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setFound({ kind: "loading" });
    load()
      .then((items) => {
        if (!cancelled) setFound(foundIn(items, id));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setFound({
          kind: "failed",
          message: err instanceof ApiError ? err.message : failure,
        });
      });
    return () => {
      cancelled = true;
    };
  }, [load, id, failure]);

  return found;
}

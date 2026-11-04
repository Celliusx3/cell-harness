"use client";

import { useEffect, useState } from "react";

const SECOND_MS = 1000;

/** Whole seconds as "m:ss", with minutes uncapped: "0:07", "1:12", "12:05". */
export function elapsedLabel(milliseconds: number): string {
  const seconds = Math.floor(Math.max(0, milliseconds) / SECOND_MS);
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

/** The time since `active` last turned true, ticking each second, or null while it is false. */
export function useElapsed(active: boolean): string | null {
  const [milliseconds, setMilliseconds] = useState(0);

  useEffect(() => {
    if (!active) return;
    const start = Date.now();
    const timer = window.setInterval(() => setMilliseconds(Date.now() - start), SECOND_MS);
    return () => {
      window.clearInterval(timer);
      setMilliseconds(0);
    };
  }, [active]);

  return active ? elapsedLabel(milliseconds) : null;
}

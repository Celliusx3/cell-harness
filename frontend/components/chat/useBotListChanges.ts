import { useEffect, useRef } from "react";

/** Calls `onChange` once connected, and after every change to the bots or groups, wherever it was made. */
export function useBotListChanges(onChange: () => void): void {
  const latest = useRef(onChange);

  useEffect(() => {
    latest.current = onChange;
  }, [onChange]);

  useEffect(() => {
    const changes = new EventSource("/api/bots/changes");
    changes.addEventListener("changed", () => latest.current());
    return () => changes.close();
  }, []);
}

import type { AutoPick } from "@/components/conversation/timelineItems";

/** The small line under a reply Auto picked: how sure it was, or that the lead answered instead. */
export function AutoPickLine({ pick }: { pick: AutoPick }) {
  const text = pick.fallback
    ? "Auto was unsure · lead answered"
    : `Picked by Auto · ${Math.round(pick.confidence * 100)}%`;
  return <p className="text-xs text-ink-soft">{text}</p>;
}

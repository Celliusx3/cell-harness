import type { Speaker } from "@/components/conversation/timelineItems";

const HUES = [25, 70, 145, 195, 250, 310];

function hueOf(id: string): number {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return HUES[hash % HUES.length] ?? 25;
}

/** A bot's initial on a circle whose color comes from its id. */
export function BotAvatar({ speaker }: { speaker: Speaker }) {
  return (
    <span
      aria-hidden
      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
      style={{ backgroundColor: `oklch(60% 0.13 ${hueOf(speaker.id)})` }}
    >
      {speaker.name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}

import type { Speaker } from "@/components/conversation/timelineItems";

export type BotMood = "awake" | "asleep" | "working";

export type BotAvatarSize = "chat" | "hero";

const SIZES: Record<BotAvatarSize, string> = {
  chat: "size-9",
  hero: "size-16",
};

const HUES = [25, 70, 145, 195, 250, 310];

function hueOf(id: string): number {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return HUES[hash % HUES.length] ?? 25;
}

interface BotAvatarProps {
  speaker: Speaker;
  mood: BotMood;
  size: BotAvatarSize;
}

/** The app's robot head on a circle colored by the bot's id: still when awake, looping when asleep or working. */
export function BotAvatar({ speaker, mood, size }: BotAvatarProps) {
  return (
    <span
      aria-hidden
      className={`flex shrink-0 items-center justify-center overflow-hidden rounded-full text-white ${SIZES[size]}`}
      style={{ backgroundColor: `oklch(48% 0.08 ${hueOf(speaker.id)})` }}
    >
      {mood === "awake" ? <BotHead /> : <BotLoop mood={mood} />}
    </span>
  );
}

function BotLoop({ mood }: { mood: Exclude<BotMood, "awake"> }) {
  return (
    <picture className="size-full">
      <source srcSet={`/bot/${mood}.png`} media="(prefers-reduced-motion: reduce)" />
      <img src={`/bot/${mood}.webp`} alt="" className="size-full" />
    </picture>
  );
}

function BotHead() {
  return (
    <svg viewBox="-100 -137 1225 1225" className="size-full" fill="currentColor">
      <rect x="227" y="290" width="570" height="444" rx="168" fill="none" stroke="currentColor" strokeWidth="64" />
      <rect x="126" y="429" width="50" height="165" rx="25" />
      <rect x="848" y="429" width="50" height="165" rx="25" />
      <path d="M357 512 H438 M586 512 H667" stroke="currentColor" strokeWidth="48" strokeLinecap="round" />
    </svg>
  );
}

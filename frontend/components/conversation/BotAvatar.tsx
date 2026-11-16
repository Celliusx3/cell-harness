export type BotMood = "awake" | "asleep" | "working";

const AVATAR_BLUE = "#2563eb";

/** The app's robot head on a blue circle: still when awake, a looping GIF when asleep or working. */
export function BotAvatar({ mood }: { mood: BotMood }) {
  return (
    <span
      aria-hidden
      className="flex size-7 shrink-0 items-center justify-center overflow-hidden rounded-full text-white"
      style={{ backgroundColor: AVATAR_BLUE }}
    >
      {mood === "awake" ? <BotHead /> : <BotLoop mood={mood} />}
    </span>
  );
}

function BotLoop({ mood }: { mood: Exclude<BotMood, "awake"> }) {
  return (
    <picture>
      <source srcSet={`/bot/${mood}.png`} media="(prefers-reduced-motion: reduce)" />
      <img src={`/bot/${mood}.gif`} alt="" className="size-7" />
    </picture>
  );
}

function BotHead() {
  return (
    <svg viewBox="-100 -137 1225 1225" className="size-7" fill="currentColor">
      <rect x="227" y="290" width="570" height="444" rx="168" fill="none" stroke="currentColor" strokeWidth="64" />
      <rect x="126" y="429" width="50" height="165" rx="25" />
      <rect x="848" y="429" width="50" height="165" rx="25" />
      <path d="M357 512 H438 M586 512 H667" stroke="currentColor" strokeWidth="48" strokeLinecap="round" />
    </svg>
  );
}

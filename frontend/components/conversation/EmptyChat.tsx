import { BotAvatar } from "@/components/conversation/BotAvatar";
import type { Speaker } from "@/components/conversation/timelineItems";

/** A chat with nothing in it yet: who it is with, and what to do first. */
export function EmptyChat({ speaker }: { speaker: Speaker | null }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
      {speaker !== null && <BotAvatar speaker={speaker} />}
      <h2 className="font-display text-2xl font-semibold tracking-tight text-balance">
        {speaker === null ? "Start the conversation" : `Ask ${speaker.name} anything`}
      </h2>
      <p className="max-w-sm text-sm text-ink-soft">
        Send a message below. Steps it takes on its tools show up here as it works.
      </p>
    </div>
  );
}

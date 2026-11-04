import type { ReactNode } from "react";

import { BotAvatar } from "@/components/conversation/BotAvatar";
import type { Speaker } from "@/components/conversation/timelineItems";

/** What a bot shows, under its avatar and name, or bare when no bot is named. */
export function BotBlock({ speaker, children }: { speaker: Speaker | null; children: ReactNode }) {
  return (
    <div className="flex gap-3">
      {speaker !== null && <BotAvatar speaker={speaker} />}
      <div className="min-w-0 flex-1 space-y-3">
        {speaker !== null && (
          <p className="text-sm font-semibold leading-7 text-ink">{speaker.name}</p>
        )}
        {children}
      </div>
    </div>
  );
}

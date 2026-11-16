import type { ReactNode } from "react";

import { BotAvatar, type BotMood } from "@/components/conversation/BotAvatar";
import type { Speaker } from "@/components/conversation/timelineItems";

interface BotBlockProps {
  speaker: Speaker | null;
  continues: boolean;
  mood: BotMood;
  children: ReactNode;
}

/** What a bot shows, under its avatar and name, or bare when no bot is named or it continues its last block. */
export function BotBlock({ speaker, continues, mood, children }: BotBlockProps) {
  const named = speaker !== null && !continues;
  return (
    <div className={`flex gap-3 ${continues ? "-mt-2" : ""}`}>
      {speaker !== null && (named ? <BotAvatar speaker={speaker} mood={mood} size="chat" /> : <span className="w-9 shrink-0" />)}
      <div className="min-w-0 flex-1 space-y-3">
        {named && (
          <p className="text-sm font-semibold leading-9 text-ink">{speaker.name}</p>
        )}
        {children}
      </div>
    </div>
  );
}

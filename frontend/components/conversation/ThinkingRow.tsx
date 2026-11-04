import { BotBlock } from "@/components/conversation/BotAvatar";
import type { Speaker } from "@/components/conversation/timelineItems";
import { Trace, TraceLine, TraceTitle } from "@/components/ui/trace";

/** A shimmering "Thinking" where the bot's answer will be, until it has something to show. */
export function ThinkingRow({ speaker }: { speaker: Speaker | null }) {
  return (
    <BotBlock speaker={speaker}>
      <Trace role="status">
        <TraceLine status="running">
          <TraceTitle>Thinking</TraceTitle>
        </TraceLine>
      </Trace>
    </BotBlock>
  );
}

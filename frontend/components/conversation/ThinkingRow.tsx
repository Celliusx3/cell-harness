import { BotBlock } from "@/components/conversation/BotAvatar";
import type { Speaker } from "@/components/conversation/timelineItems";
import { Trace, TraceDescription, TraceLine, TraceTitle } from "@/components/ui/trace";

/** A shimmering "Thinking" where the bot's answer will be, until it has something to show. */
export function ThinkingRow({
  speaker,
  elapsed,
}: {
  speaker: Speaker | null;
  elapsed: string | null;
}) {
  return (
    <BotBlock speaker={speaker}>
      <Trace role="status">
        <TraceLine status="running">
          <TraceTitle>Thinking</TraceTitle>
          {elapsed !== null && <TraceDescription aria-hidden>{elapsed}</TraceDescription>}
        </TraceLine>
      </Trace>
    </BotBlock>
  );
}

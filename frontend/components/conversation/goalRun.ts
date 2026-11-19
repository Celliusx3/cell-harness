/** A goal run in the log -> the line that opens it and the card that shows how it ended. */

import type { GoalItem } from "@/components/conversation/timelineItems";
import type { GoalStatus } from "@/lib/groupTypes";
import type { SessionEvent } from "@/lib/types";

type GoalStart = Extract<SessionEvent, { type: "goal/start" }>;

export const GOAL_STATUS_WORDS: Record<GoalStatus, string> = {
  done: "Done",
  needs_you: "Needs you",
  blocked: "Blocked",
  limit_reached: "Turn limit reached",
  stopped: "Stopped",
  failed: "Failed",
};

/** Each `goal/start` and `goal/end` among `events`, by index, as the item the timeline shows. */
export function goalItems(events: SessionEvent[]): ReadonlyMap<number, GoalItem> {
  const names = botNames(events);
  const items = new Map<number, GoalItem>();
  let start: GoalStart | null = null;
  for (const [index, event] of events.entries()) {
    if (event.type === "goal/start") {
      start = event;
      const lead = names.get(event.lead_id) ?? null;
      items.set(index, { kind: "goalStart", key: `gs${index}`, goal: event.goal, lead });
    } else if (event.type === "goal/end" && start !== null) {
      items.set(index, {
        kind: "goalEnd",
        key: `ge${index}`,
        goal: start.goal,
        lead: names.get(start.lead_id) ?? null,
        turnsUsed: event.turns_used,
        maxTurns: start.max_turns,
        status: event.status,
        detail: event.detail,
      });
    }
  }
  return items;
}

/** The name each bot answered under in `events`, by its id. */
function botNames(events: SessionEvent[]): ReadonlyMap<string, string> {
  return new Map(
    events.flatMap((event): [string, string][] =>
      event.type === "bot/instructions" && event.bot_id ? [[event.bot_id, event.name]] : [],
    ),
  );
}

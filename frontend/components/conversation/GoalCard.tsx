import { Target } from "lucide-react";

import { GOAL_STATUS_WORDS } from "@/components/conversation/goalRun";
import type { GoalEndItem } from "@/components/conversation/timelineItems";
import type { GoalStatus } from "@/lib/groupTypes";

const STATUS_TONES: Record<GoalStatus, string> = {
  done: "text-accent",
  needs_you: "text-ink",
  blocked: "text-danger",
  limit_reached: "text-ink",
  stopped: "text-ink-soft",
  failed: "text-danger",
};

/** How a goal run ended: its goal, lead, the turns it used, its status and why. */
export function GoalCard({ item }: { item: GoalEndItem }) {
  const facts = [item.lead, `${item.turnsUsed} of ${item.maxTurns} turns`].filter(
    (fact) => fact !== null,
  );
  return (
    <div className="space-y-1.5 rounded-lg border border-line bg-surface p-3 text-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="flex min-w-0 items-center gap-1.5 text-xs text-ink-soft">
          <Target size={13} aria-hidden className="shrink-0" />
          {facts.join(" · ")}
        </span>
        <span className={`shrink-0 text-xs font-medium ${STATUS_TONES[item.status]}`}>
          {GOAL_STATUS_WORDS[item.status]}
        </span>
      </div>
      <p className="break-words font-medium text-ink">{item.goal}</p>
      <p className="break-words text-ink-soft">{item.detail}</p>
    </div>
  );
}

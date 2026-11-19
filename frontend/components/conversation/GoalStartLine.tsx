import { Target } from "lucide-react";

import type { GoalStartItem } from "@/components/conversation/timelineItems";

/** A goal run starting, as a divider with its lead and goal. */
export function GoalStartLine({ item }: { item: GoalStartItem }) {
  return (
    <div className="flex flex-col gap-1 text-xs text-ink-soft">
      <div className="flex items-center gap-3">
        <span aria-hidden className="h-px flex-1 bg-line" />
        <span className="flex items-center gap-1.5">
          <Target size={13} aria-hidden className="shrink-0" />
          {item.lead === null ? "Goal run" : `Goal run · led by ${item.lead}`}
        </span>
        <span aria-hidden className="h-px flex-1 bg-line" />
      </div>
      <p className="break-words text-center">{item.goal}</p>
    </div>
  );
}

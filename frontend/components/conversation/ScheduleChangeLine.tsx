import { CalendarClock } from "lucide-react";

import type { ScheduleChange } from "@/components/conversation/timelineItems";

const VERBS: Record<ScheduleChange["change"], string> = {
  updated: "changed",
  deleted: "deleted",
};

/** A schedule of this chat's bot changed from Settings, as a divider like a mode switch. */
export function ScheduleChangeLine({ change }: { change: ScheduleChange }) {
  return (
    <div className="flex items-center gap-3 text-xs text-ink-soft">
      <span aria-hidden className="h-px flex-1 bg-line" />
      <span className="flex min-w-0 items-center gap-1.5">
        <CalendarClock size={13} aria-hidden className="shrink-0" />
        <span className="break-words">
          {`Schedule "${change.title}" was ${VERBS[change.change]} from Settings`}
        </span>
      </span>
      <span aria-hidden className="h-px flex-1 bg-line" />
    </div>
  );
}

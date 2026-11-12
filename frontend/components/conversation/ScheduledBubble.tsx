import { Clock } from "lucide-react";

import type { Reminder, ScheduledItem } from "@/components/conversation/timelineItems";
import { localTime } from "@/lib/localTime";

/** A message a schedule sent: on the person's side, outlined so it does not read as typed. */
export function ScheduledBubble({ item }: { item: ScheduledItem }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] divide-y divide-line rounded-2xl rounded-br-md border border-line bg-surface text-sm text-ink">
        {item.reminders.map((reminder) => (
          <ReminderEntry key={`${reminder.schedule_id}:${reminder.occurrence_at}`} reminder={reminder} />
        ))}
      </div>
    </div>
  );
}

function ReminderEntry({ reminder }: { reminder: Reminder }) {
  return (
    <div className="flex flex-col gap-1 px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-x-1.5 text-xs text-ink-soft">
        <Clock size={13} aria-hidden />
        <span>Scheduled</span>
        <span aria-hidden>·</span>
        <span className="break-words font-medium text-ink">{reminder.title}</span>
        <span aria-hidden>·</span>
        <time dateTime={reminder.occurrence_at}>{localTime(reminder.occurrence_at)}</time>
      </div>
      <p className="whitespace-pre-wrap break-words">{reminder.prompt}</p>
    </div>
  );
}

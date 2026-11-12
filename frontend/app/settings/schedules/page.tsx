"use client";

import { useCallback, useEffect, useState } from "react";

import { DrawerButton } from "@/components/chat/Drawer";
import { ApiError } from "@/lib/api";
import { localTime } from "@/lib/localTime";
import {
  deleteSchedule,
  listSchedules,
  pauseSchedule,
  resumeSchedule,
  runScheduleNow,
  type ScheduleRow,
} from "@/lib/schedules";

const EMPTY =
  'No schedules yet. Ask a bot to do something on a schedule, such as "every weekday at 9, check the deployment".';

/** Every bot's schedules, each with a way to pause or resume it, run it now, or delete it. */
export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<ScheduleRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setSchedules(await listSchedules());
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Could not load schedules.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const act = async (action: () => Promise<void>, failure: string) => {
    try {
      await action();
    } catch (err: unknown) {
      await refresh();
      setError(err instanceof ApiError ? err.message : failure);
      return;
    }
    await refresh();
  };

  const remove = (schedule: ScheduleRow) => {
    if (!window.confirm(`Delete the schedule "${schedule.title}" for good?`)) return;
    void act(() => deleteSchedule(schedule.id), "Could not delete.");
  };

  return (
    <>
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-4 py-5 md:px-6">
        <DrawerButton />
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold tracking-tight">Schedules</h1>
          <p className="text-sm text-ink-soft">Tasks your bots run on their own, each in its own chat.</p>
        </div>
        <span className="shrink-0 self-end text-xs text-ink-soft">{schedules.length} scheduled</span>
      </header>

      {error && (
        <div className="border-b border-danger/30 bg-danger-soft px-6 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {schedules.length === 0 ? (
          <p className="text-sm text-ink-soft">{EMPTY}</p>
        ) : (
          <ul className="max-w-2xl divide-y divide-line rounded-xl border border-line bg-surface-sunken">
            {schedules.map((schedule) => (
              <ScheduleItem
                key={schedule.id}
                schedule={schedule}
                onPause={() => void act(() => pauseSchedule(schedule.id), "Could not pause.")}
                onResume={() => void act(() => resumeSchedule(schedule.id), "Could not resume.")}
                onRunNow={() => void act(() => runScheduleNow(schedule.id), "Could not run.")}
                onDelete={() => remove(schedule)}
              />
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

interface ScheduleItemProps {
  schedule: ScheduleRow;
  onPause: () => void;
  onResume: () => void;
  onRunNow: () => void;
  onDelete: () => void;
}

function ScheduleItem({ schedule, onPause, onResume, onRunNow, onDelete }: ScheduleItemProps) {
  return (
    <li className="flex flex-col gap-2 px-3 py-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="break-words font-medium">{schedule.title}</span>
        <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 text-[11px] text-ink-soft">
          {schedule.status}
        </span>
        <span className="text-xs text-ink-soft">{schedule.bot_name}</span>
      </div>
      <Times schedule={schedule} />
      <p className="whitespace-pre-wrap break-words text-ink">{schedule.prompt}</p>
      <div className="flex flex-wrap gap-2">
        {schedule.status === "active" && <RowButton label="Pause" onClick={onPause} />}
        {schedule.status === "paused" && <RowButton label="Resume" onClick={onResume} />}
        <RowButton label="Run now" onClick={onRunNow} />
        <RowButton label="Delete" onClick={onDelete} />
      </div>
    </li>
  );
}

function Times({ schedule }: { schedule: ScheduleRow }) {
  const next = schedule.status === "active" ? schedule.scheduled_at : null;
  const last = schedule.last_occurrence_at;
  return (
    <div className="flex flex-wrap gap-x-4 text-xs text-ink-soft">
      {next !== null && (
        <span>
          Next <time dateTime={next}>{localTime(next)}</time>
        </span>
      )}
      <span>
        Last run {last === null ? "never" : <time dateTime={last}>{localTime(last)}</time>}
      </span>
    </div>
  );
}

function RowButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border border-line bg-surface px-3 py-1 text-xs font-medium transition hover:bg-surface-sunken"
    >
      {label}
    </button>
  );
}

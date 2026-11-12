import { request } from "./api";

/** Where a schedule stands: running on its times, held until resumed, or with no time left. */
export type ScheduleStatus = "active" | "paused" | "ended";

/** One row of `GET /api/schedules`, its times ISO UTC. */
export interface ScheduleRow {
  id: string;
  bot_id: string;
  bot_name: string;
  title: string;
  prompt: string;
  rrule: string;
  status: ScheduleStatus;
  scheduled_at: string;
  last_occurrence_at: string | null;
  created_at: string;
}

const path = (id: string, action = "") => `/schedules/${encodeURIComponent(id)}${action}`;

/** Every bot's schedules: active by next time, then paused and ended, newest first. */
export const listSchedules = () => request<ScheduleRow[]>("/schedules");

export const pauseSchedule = (id: string) => request<void>(path(id, "/pause"), { method: "POST" });

export const resumeSchedule = (id: string) => request<void>(path(id, "/resume"), { method: "POST" });

/** Deliver the schedule at once; its next time stays where it was. */
export const runScheduleNow = (id: string) => request<void>(path(id, "/run"), { method: "POST" });

export const deleteSchedule = (id: string) => request<void>(path(id), { method: "DELETE" });

"use client";

import { useMemo } from "react";

import { buildTimeline } from "@/components/conversation/buildTimeline";
import type { Timeline } from "@/components/conversation/timelineItems";
import type { SessionEvent } from "@/lib/types";

/** The timeline for a set of events, recomputed only when they change. */
export function useTimeline(events: SessionEvent[]): Timeline {
  return useMemo(() => buildTimeline(events), [events]);
}

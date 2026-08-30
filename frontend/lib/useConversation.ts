"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, getConversation, sendMessage, stopRun } from "./api";
import { streamEvents } from "./stream";
import { buildTimeline } from "./timeline";
import type { SessionEvent } from "./types";

/**
 * One conversation: its events, whether a turn is running, and how to act on it.
 *
 * The order here is the protocol, and it is the reason a refresh mid-turn loses
 * nothing:
 *
 *   1. fetch the snapshot          -> events 0..n, `next_cursor` = n
 *   2. stream from `next_cursor`   -> n onward, live
 *
 * Snapshot first cannot lose an event; the reverse can deliver one twice. The
 * cursor is a session sequence number, so it means the same thing to both.
 */

/** Waited before reconnecting a dropped stream, so a flapping link cannot spin. */
const RECONNECT_DELAY_MS = 500;

export interface Conversation {
  events: SessionEvent[];
  /**
   * Messages sent while a turn was running, not yet in the log.
   *
   * The server holds them and answers them next; they become one `user/message`
   * when that turn starts. Until then nothing on the server can render them, so
   * they are shown from here — otherwise text someone just sent would vanish
   * from the screen until the current answer finished.
   */
  queued: string[];
  title: string;
  running: boolean;
  loading: boolean;
  error: string | null;
  send(prompt: string): Promise<void>;
  stop(): Promise<void>;
}

export function useConversation(conversationId: string): Conversation {
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [queued, setQueued] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * The cursor lives in a ref, not state.
   *
   * It is advanced from inside the streaming loop, which would otherwise be
   * reading a value captured when the effect ran — and a stale cursor is exactly
   * the bug that loses or repeats events.
   */
  const cursor = useRef(0);

  /**
   * Wakes the follow loop when it is parked between turns. Null while a turn
   * runs — the stream is open then, so there is nothing to wake.
   */
  const resume = useRef<(() => void) | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    setEvents([]);
    setQueued([]);
    setRunning(false);
    setLoading(true);
    setError(null);
    cursor.current = 0;

    const follow = async () => {
      try {
        const detail = await getConversation(conversationId);
        if (cancelled) return;
        setEvents(detail.events);
        setTitle(detail.title);
        setRunning(detail.running);
        setLoading(false);
        cursor.current = detail.next_cursor;
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "could not load this conversation");
        setLoading(false);
        return;
      }

      // Follow the conversation for as long as it is on screen. A `dropped`
      // ending — a sleeping laptop, a dying link — resumes at the cursor, which
      // is what makes "close the tab, come back, it's still running" work.
      for (;;) {
        let ended = false;
        await streamEvents(conversationId, cursor.current, controller.signal, {
          onEvent(event) {
            cursor.current += 1;
            setEvents((previous) => [...previous, event]);
            // The queue drains as *one* turn — the server joins it with
            // newlines — so a single `user/message` accounts for all of it, and
            // clearing the lot is right rather than lazy. Three bubbles becoming
            // one is what the model actually saw.
            if (event.type === "user/message") setQueued([]);
            setRunning(true);
          },
          onEnd(end) {
            ended = end.kind !== "dropped";
            if (end.kind === "end") setRunning(false);
          },
        });
        if (cancelled || controller.signal.aborted) break;

        if (ended) {
          // Park rather than break or reconnect. Breaking left every turn after
          // the first invisible — the effect only re-runs on `conversationId`.
          // Reconnecting would spin: an idle conversation answers `end` at once.
          await new Promise<void>((resolve) => {
            resume.current = resolve;
          });
          resume.current = null;
          if (cancelled || controller.signal.aborted) break;
          continue; // no delay — a wake means a turn started, not a flaky link
        }

        await new Promise((resolve) => setTimeout(resolve, RECONNECT_DELAY_MS));
        if (cancelled || controller.signal.aborted) break;
      }
    };

    void follow();
    return () => {
      cancelled = true;
      controller.abort();
      // A parked loop is in no fetch, so `abort` alone would leave it waiting
      // forever. It re-checks `cancelled` the moment it wakes.
      resume.current?.();
    };
  }, [conversationId]);

  const send = useCallback(
    async (prompt: string) => {
      setError(null);
      try {
        const accepted = await sendMessage(conversationId, prompt);
        // A started turn appends nothing here: its `user/message` arrives on the
        // stream the effect is already holding open, so the screen shows what the
        // log says. A *queued* message has no log entry to wait for, which is the
        // one case the client has to render for itself.
        if (accepted.queued) setQueued((previous) => [...previous, prompt]);
        setRunning(true);
        // Wake the loop if the last turn left it parked. Safe after the await:
        // the run is registered before the `202`, so the subscribe cannot miss it.
        resume.current?.();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "could not send that message");
      }
    },
    [conversationId],
  );

  const stop = useCallback(async () => {
    try {
      await stopRun(conversationId);
    } catch (err) {
      // A 404 means it finished between the click and the request. Not worth
      // showing: the user asked for it to stop and it has.
      if (!(err instanceof ApiError && err.status === 404)) {
        setError(err instanceof ApiError ? err.message : "could not stop this turn");
      }
    }
  }, [conversationId]);

  return { events, queued, title, running, loading, error, send, stop };
}

/** The timeline for a set of events, recomputed only when they change. */
export function useTimeline(events: SessionEvent[]) {
  return useMemo(() => buildTimeline(events), [events]);
}

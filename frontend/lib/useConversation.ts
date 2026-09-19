"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  compactConversation,
  getConversation,
  sendMessage,
  stopRun,
} from "./api";
import { streamEvents } from "./stream";
import { buildTimeline } from "./timeline";
import type { SessionEvent } from "./types";

/** One conversation: its events, whether a turn is running, and how to act on it. */

/** The wait before reconnecting a dropped stream. */
const RECONNECT_DELAY_MS = 500;

export interface Conversation {
  events: SessionEvent[];
  /** Messages sent while a turn was running, not yet in the log. */
  queued: string[];
  title: string;
  running: boolean;
  loading: boolean;
  error: string | null;
  send(prompt: string): Promise<void>;
  stop(): Promise<void>;
  /** Compact the conversation now; the summary lands via the stream. */
  compact(): Promise<void>;
  /** A turn was started by something other than `send` */
  wake(): void;
}

export function useConversation(conversationId: string): Conversation {
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [queued, setQueued] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cursor = useRef(0);

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
        setError(
          err instanceof ApiError
            ? err.message
            : "could not load this conversation",
        );
        setLoading(false);
        return;
      }

      for (;;) {
        let ended = false;
        await streamEvents(conversationId, cursor.current, controller.signal, {
          onEvent(event) {
            cursor.current += 1;
            setEvents((previous) => [...previous, event]);
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
          await new Promise<void>((resolve) => {
            resume.current = resolve;
          });
          resume.current = null;
          if (cancelled || controller.signal.aborted) break;
          continue;
        }

        await new Promise((resolve) => setTimeout(resolve, RECONNECT_DELAY_MS));
        if (cancelled || controller.signal.aborted) break;
      }
    };

    void follow();
    return () => {
      cancelled = true;
      controller.abort();
      resume.current?.();
    };
  }, [conversationId]);

  /** A turn was just started elsewhere */
  const wake = useCallback(() => {
    setRunning(true);
    resume.current?.();
  }, []);

  const send = useCallback(
    async (prompt: string) => {
      setError(null);
      try {
        const accepted = await sendMessage(conversationId, prompt);
        if (accepted.queued) setQueued((previous) => [...previous, prompt]);
        wake();
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "could not send that message",
        );
      }
    },
    [conversationId, wake],
  );

  const compact = useCallback(async () => {
    try {
      await compactConversation(conversationId);
      wake();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "could not compact this conversation",
      );
    }
  }, [conversationId, wake]);

  const stop = useCallback(async () => {
    try {
      await stopRun(conversationId);
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 404)) {
        setError(
          err instanceof ApiError ? err.message : "could not stop this turn",
        );
      }
    }
  }, [conversationId]);

  return { events, queued, title, running, loading, error, send, stop, compact, wake };
}

/** The timeline for a set of events, recomputed only when they change. */
export function useTimeline(events: SessionEvent[]) {
  return useMemo(() => buildTimeline(events), [events]);
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  clearConversation,
  compactConversation,
  getConversation,
  sendMessage,
  setConversationMode,
  stopRun,
} from "@/lib/api";
import { streamEvents } from "@/lib/stream";
import type { ApprovalMode, SessionEvent, ChatFile } from "@/lib/types";

/** One conversation: its events, whether a turn is running, and how to act on it. */

/** The wait before reconnecting a dropped stream. */
const RECONNECT_DELAY_MS = 500;

export interface Conversation {
  events: SessionEvent[];
  /** Messages sent while a turn was running, not yet in the log. */
  queued: string[];
  /** The prompt pressed, until the log holds it, the server queues it, the send fails, or the stream ends. */
  sending: string | null;
  running: boolean;
  /** The mode the chat's next call runs under, or null until the chat has loaded. */
  mode: ApprovalMode | null;
  loading: boolean;
  error: string | null;
  send(prompt: string, files: ChatFile[]): Promise<void>;
  stop(): Promise<void>;
  /** Compact the conversation now; the summary lands via the stream. */
  compact(): Promise<void>;
  /** Clear the chat in place; the clear lands via the stream. */
  clear(): Promise<void>;
  /** Switch what asks in this chat; the switch lands in the timeline via the stream. */
  switchMode(mode: ApprovalMode): Promise<void>;
  /** A turn was started by something other than `send` */
  wake(): void;
  /** Read anything logged since the cursor, without showing a turn as running */
  catchUp(): void;
}

export function useConversation(conversationId: string): Conversation {
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [queued, setQueued] = useState<string[]>([]);
  const [sending, setSending] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [mode, setMode] = useState<ApprovalMode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cursor = useRef(0);

  const resume = useRef<(() => void) | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    setEvents([]);
    setQueued([]);
    setSending(null);
    setRunning(false);
    setMode(null);
    setLoading(true);
    setError(null);
    cursor.current = 0;

    const follow = async () => {
      try {
        const detail = await getConversation(conversationId);
        if (cancelled) return;
        setEvents(detail.events);
        setRunning(detail.running);
        setMode(detail.mode);
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
          onEvent(event, number) {
            cursor.current = number + 1;
            setEvents((previous) => [...previous, event]);
            if (event.type === "user/message") {
              setQueued([]);
              setSending(null);
            }
            if (event.type === "approval/mode") setMode(event.mode);
            else setRunning(true);
          },
          onEnd(end) {
            ended = end.kind !== "dropped";
            if (end.kind !== "end") return;
            setRunning(false);
            setSending(null);
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

  const catchUp = useCallback(() => {
    resume.current?.();
  }, []);

  const send = useCallback(
    async (prompt: string, files: ChatFile[]) => {
      setError(null);
      setSending(prompt);
      try {
        const accepted = await sendMessage(conversationId, prompt, files);
        if (accepted.queued) {
          setSending(null);
          setQueued((previous) => [...previous, prompt]);
        }
        wake();
      } catch (err) {
        setSending(null);
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

  const clear = useCallback(async () => {
    try {
      await clearConversation(conversationId);
      setQueued([]);
      wake();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "could not clear this chat");
    }
  }, [conversationId, wake]);

  const switchMode = useCallback(
    async (next: ApprovalMode) => {
      setError(null);
      try {
        await setConversationMode(conversationId, next);
        setMode(next);
        catchUp();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "could not switch this chat's mode");
      }
    },
    [conversationId, catchUp],
  );

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

  return {
    events,
    queued,
    sending,
    running,
    mode,
    loading,
    error,
    send,
    stop,
    compact,
    clear,
    switchMode,
    wake,
    catchUp,
  };
}

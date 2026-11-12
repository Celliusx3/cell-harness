"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type Control,
  keepAwake,
  releaseControl,
  takeControl,
  viewScreen,
} from "@/components/computer/screen";
import type { ScreenServer } from "@/components/computer/server";

/** What the person asks of a screen: watch it, hold it, or hand it back. */
type ScreenChange = "view" | "control" | "release";

/** A change that did not go through, what was said, and the change to try again. */
interface FailedChange {
  message: string;
  retry: ScreenChange;
}

/** One screen as the page holds it: its page, the person's control of it, and how a change went. */
export interface Screen {
  url: string | null;
  control: Control | null;
  error: FailedChange | null;
  busy: boolean;
  change: (change: ScreenChange) => Promise<void>;
}

const KEEP_AWAKE_MS = 60_000;

function messageOf(err: unknown, server: ScreenServer): string {
  return err instanceof Error ? err.message : `The ${server.id} could not be reached.`;
}

/** A server's screen, opened with `first`, kept awake, and watched again when control runs out. */
export function useScreen(server: ScreenServer, first: ScreenChange): Screen {
  const [viewUrl, setViewUrl] = useState<string | null>(null);
  const [control, setControl] = useState<Control | null>(null);
  const [error, setError] = useState<FailedChange | null>(null);
  const [busy, setBusy] = useState(false);

  const change = useCallback(
    async (wanted: ScreenChange) => {
      setBusy(true);
      setError(null);
      try {
        if (wanted === "control") {
          setControl(await takeControl(server));
          return;
        }
        if (wanted === "release") await releaseControl(server);
        const opened = await viewScreen(server);
        setControl(opened.control);
        setViewUrl(opened.url);
      } catch (err: unknown) {
        setError({ message: messageOf(err, server), retry: wanted });
      } finally {
        setBusy(false);
      }
    },
    [server],
  );

  useEffect(() => {
    void change(first);
  }, [change, first]);

  useEffect(() => {
    const timer = window.setInterval(() => void keepAwake(server).catch(() => {}), KEEP_AWAKE_MS);
    return () => window.clearInterval(timer);
  }, [server]);

  useEffect(() => {
    if (control === null) return;
    const timer = window.setTimeout(() => void change("view"), control.until.getTime() - Date.now());
    return () => window.clearTimeout(timer);
  }, [control, change]);

  return { url: control?.url ?? viewUrl, control, error, busy, change };
}

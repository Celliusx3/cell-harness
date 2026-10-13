"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";

import { FilesPanel } from "@/components/computer/FilesPanel";
import {
  type Control,
  keepAwake,
  releaseControl,
  takeControl,
  viewScreen,
} from "@/components/computer/screen";

const TerminalPanel = dynamic(
  () => import("@/components/computer/TerminalPanel").then((m) => m.TerminalPanel),
  { ssr: false },
);

type ScreenChange = "view" | "control" | "release";
type Panel = "terminal" | "files";

const KEEP_AWAKE_MS = 60_000;

interface FailedChange {
  message: string;
  retry: ScreenChange;
}

const BUTTON =
  "rounded-md border border-line px-2 py-0.5 text-xs text-ink-soft transition hover:text-ink disabled:opacity-40";

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : "The computer could not be reached.";
}

function clockTime(at: Date): string {
  return at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

/** The shared computer's screen, live: viewed, or controlled by the person for a while. */
export default function ComputerPage() {
  const [viewUrl, setViewUrl] = useState<string | null>(null);
  const [control, setControl] = useState<Control | null>(null);
  const [error, setError] = useState<FailedChange | null>(null);
  const [busy, setBusy] = useState(false);
  const [panel, setPanel] = useState<Panel | null>(null);

  const changeScreen = useCallback(async (change: ScreenChange) => {
    setBusy(true);
    setError(null);
    try {
      if (change === "control") {
        setControl(await takeControl());
        return;
      }
      if (change === "release") await releaseControl();
      setControl(null);
      setPanel((open) => (open === "terminal" ? null : open));
      setViewUrl(await viewScreen());
    } catch (err: unknown) {
      setError({ message: messageOf(err), retry: change });
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void changeScreen("control");
  }, [changeScreen]);

  useEffect(() => {
    const timer = window.setInterval(() => void keepAwake().catch(() => {}), KEEP_AWAKE_MS);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (control === null) return;
    const timer = window.setTimeout(
      () => void changeScreen("view"),
      control.until.getTime() - Date.now(),
    );
    return () => window.clearTimeout(timer);
  }, [control, changeScreen]);

  const toggle = (chosen: Panel) => setPanel((open) => (open === chosen ? null : chosen));

  const screenUrl = control?.url ?? viewUrl;
  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-4 py-2">
        <h1 className="min-w-0 truncate text-sm font-medium">Computer</h1>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => toggle("terminal")}
            disabled={control === null}
            aria-pressed={panel === "terminal"}
            title={control === null ? "Take control first" : "A shell on the computer"}
            className={panel === "terminal" ? `${BUTTON} text-ink` : BUTTON}
          >
            Terminal
          </button>
          <button
            type="button"
            onClick={() => toggle("files")}
            aria-pressed={panel === "files"}
            title="The computer's home folder"
            className={panel === "files" ? `${BUTTON} text-ink` : BUTTON}
          >
            Files
          </button>
          {control === null ? (
            <button
              type="button"
              onClick={() => void changeScreen("control")}
              disabled={busy}
              title="Use your own mouse, keyboard and paste on the computer"
              className={BUTTON}
            >
              Take control
            </button>
          ) : (
            <>
              <span className="text-xs text-ink-soft">
                You have control until {clockTime(control.until)}
              </span>
              <button
                type="button"
                onClick={() => void changeScreen("release")}
                disabled={busy}
                title="Hand the screen back to the bots"
                className={BUTTON}
              >
                Release
              </button>
            </>
          )}
        </div>
      </header>

      {error !== null && (
        <div className="flex items-center gap-3 border-b border-danger/30 bg-danger-soft px-4 py-2 text-sm text-danger">
          <p className="min-w-0 flex-1 break-words">{error.message}</p>
          <button type="button" onClick={() => void changeScreen(error.retry)} className={BUTTON}>
            Retry
          </button>
        </div>
      )}

      {control === null && screenUrl !== null && (
        <p className="border-b border-line bg-surface-sunken px-4 py-1.5 text-xs text-ink-soft">
          Watching only. Press Take control to use your keyboard and mouse.
        </p>
      )}

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {screenUrl === null ? (
            busy && <p className="px-6 py-6 text-sm text-ink-soft">Starting the computer…</p>
          ) : (
            <iframe
              key={screenUrl}
              src={screenUrl}
              title="The computer's screen"
              sandbox="allow-scripts allow-pointer-lock"
              allow="clipboard-read; clipboard-write"
              className="block min-h-0 w-full flex-1 border-0"
            />
          )}
        </div>
        {panel !== null && (
          <aside className="flex min-h-0 w-[36rem] max-w-[50%] shrink-0 flex-col border-l border-line">
            {panel === "terminal" ? <TerminalPanel /> : <FilesPanel canUpload={control !== null} />}
          </aside>
        )}
      </div>
    </>
  );
}

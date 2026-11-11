"use client";

import type { Screen } from "@/components/computer/useScreen";

export const BUTTON =
  "rounded-md border border-line px-2 py-0.5 text-xs text-ink-soft transition hover:text-ink disabled:opacity-40";

function clockTime(at: Date): string {
  return at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

/** Take control of a screen, or see until when it is held and hand it back. */
export function ScreenControls({
  screen,
  takeTitle,
  releaseTitle,
}: {
  screen: Screen;
  takeTitle: string;
  releaseTitle: string;
}) {
  if (screen.control === null) {
    return (
      <button
        type="button"
        onClick={() => void screen.change("control")}
        disabled={screen.busy}
        title={takeTitle}
        className={BUTTON}
      >
        Take control
      </button>
    );
  }
  return (
    <>
      <span className="text-xs text-ink-soft">
        You have control until {clockTime(screen.control.until)}
      </span>
      <button
        type="button"
        onClick={() => void screen.change("release")}
        disabled={screen.busy}
        title={releaseTitle}
        className={BUTTON}
      >
        Release
      </button>
    </>
  );
}

/** Why the last change failed, with a way to try it again; then whether the screen is only watched. */
export function ScreenNotices({ screen }: { screen: Screen }) {
  const { error } = screen;
  return (
    <>
      {error !== null && (
        <div className="flex items-center gap-3 border-b border-danger/30 bg-danger-soft px-4 py-2 text-sm text-danger">
          <p className="min-w-0 flex-1 break-words">{error.message}</p>
          <button type="button" onClick={() => void screen.change(error.retry)} className={BUTTON}>
            Retry
          </button>
        </div>
      )}
      {screen.control === null && screen.url !== null && (
        <p className="border-b border-line bg-surface-sunken px-4 py-1.5 text-xs text-ink-soft">
          Watching only. Press Take control to use your keyboard and mouse.
        </p>
      )}
    </>
  );
}

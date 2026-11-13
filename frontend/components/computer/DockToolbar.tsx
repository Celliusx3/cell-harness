"use client";

import { Maximize, MousePointer2 } from "lucide-react";
import Link from "next/link";

import { clockTime } from "@/components/computer/ScreenControls";
import type { Screen } from "@/components/computer/useScreen";

export type View = "screen" | "terminal" | "files";

const VIEWS: { view: View; label: string }[] = [
  { view: "screen", label: "Screen" },
  { view: "terminal", label: "Terminal" },
  { view: "files", label: "Files" },
];

const TAB = "h-8 rounded-lg px-3.5 text-[13px] font-medium transition disabled:opacity-40";
const TAB_ON = `${TAB} bg-surface-raised text-ink shadow-sm`;
const TAB_OFF = `${TAB} text-ink-soft hover:text-ink`;
const BUTTON =
  "inline-flex h-9 shrink-0 items-center gap-2 rounded-[10px] px-3.5 text-[13px] font-medium transition disabled:opacity-40";

interface DockToolbarProps {
  screen: Screen;
  view: View;
  onView(view: View): void;
}

/** The dock's tabs, what the screen is doing, and the one action that matters right now. */
export function DockToolbar({ screen, view, onView }: DockToolbarProps) {
  const held = screen.control !== null;
  return (
    <div className="flex min-h-14 items-center gap-2 border-b border-line px-3.5 py-2">
      <div role="tablist" aria-label="Computer view" className="flex shrink-0 gap-0.5 rounded-[10px] bg-surface-sunken p-0.5">
        {VIEWS.map(({ view: option, label }) => (
          <button
            key={option}
            type="button"
            role="tab"
            aria-selected={view === option}
            disabled={option === "terminal" && !held}
            title={option === "terminal" && !held ? "Take control first" : undefined}
            onClick={() => onView(option)}
            className={view === option ? TAB_ON : TAB_OFF}
          >
            {label}
          </button>
        ))}
      </div>
      {held ? <HeldControls screen={screen} /> : <WatchingControls screen={screen} />}
      <Link
        href="/computer"
        aria-label="Open full screen"
        title="Open full screen"
        className="flex size-9 shrink-0 items-center justify-center rounded-[10px] text-ink-soft transition hover:bg-surface-sunken hover:text-ink"
      >
        <Maximize size={17} />
      </Link>
    </div>
  );
}

function WatchingControls({ screen }: { screen: Screen }) {
  const status = screenStatus(screen);
  return (
    <>
      <span className="ml-1.5 flex min-w-0 items-center gap-1.5 text-xs text-ink-soft">
        <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-accent" />
        <span>{status}</span>
      </span>
      <button
        type="button"
        onClick={() => void screen.change("control")}
        disabled={screen.busy}
        title="Use your own mouse, keyboard and paste on the computer"
        className={`${BUTTON} ml-auto bg-action text-on-action hover:opacity-90`}
      >
        <MousePointer2 size={15} />
        Take control
      </button>
    </>
  );
}

function screenStatus(screen: Screen): string {
  if (screen.url !== null) return "Watching live";
  return screen.error === null ? "Starting…" : "Not running";
}

function HeldControls({ screen }: { screen: Screen }) {
  const until = screen.control === null ? "" : clockTime(screen.control.until);
  return (
    <>
      <span className="ml-auto inline-flex min-h-7 min-w-0 items-center gap-1.5 rounded-full bg-attention-soft px-2.5 py-1 text-xs font-medium text-attention">
        <MousePointer2 size={13} className="shrink-0" />
        You&apos;re in control · until {until}
      </span>
      <button
        type="button"
        onClick={() => void screen.change("release")}
        disabled={screen.busy}
        title="Hand the screen back to the bots"
        className={`${BUTTON} border border-line bg-surface-raised text-ink hover:bg-surface-sunken`}
      >
        Hand back
      </button>
    </>
  );
}

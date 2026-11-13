"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { DockToolbar, type View } from "@/components/computer/DockToolbar";
import { FilesPanel } from "@/components/computer/FilesPanel";
import { COMPUTER_SCREEN } from "@/components/computer/server";
import { type Screen, useScreen } from "@/components/computer/useScreen";

const TerminalPanel = dynamic(
  () => import("@/components/computer/TerminalPanel").then((m) => m.TerminalPanel),
  { ssr: false },
);

/** The computer docked beside a chat: its screen, a shell and its files, one at a time. */
export function ComputerDock() {
  const screen = useScreen(COMPUTER_SCREEN, "view");
  const [view, setView] = useState<View>("screen");
  const { control } = screen;

  useEffect(() => {
    if (control === null) setView((shown) => (shown === "terminal" ? "screen" : shown));
  }, [control]);

  return (
    <section
      aria-label="Computer"
      className="hidden min-h-0 w-1/2 max-w-[56rem] shrink-0 flex-col border-l border-line bg-surface-raised lg:flex"
    >
      <DockToolbar screen={screen} view={view} onView={setView} />
      <DockError screen={screen} />
      <div className="flex min-h-0 flex-1 flex-col">
        <div className={view === "screen" ? "flex min-h-0 flex-1 flex-col gap-2.5 bg-surface-sunken p-3.5" : "hidden"}>
          <div className="flex min-h-0 flex-1 overflow-hidden rounded-xl border border-line bg-neutral-900">
            {screen.url !== null && (
              <iframe
                key={screen.url}
                src={screen.url}
                title="The computer's screen"
                sandbox="allow-scripts allow-pointer-lock"
                allow="clipboard-read; clipboard-write"
                className="block min-h-0 w-full flex-1 border-0"
              />
            )}
          </div>
          <p className="text-xs text-ink-soft">Linux desktop · Chrome · Kept awake while open</p>
        </div>
        {view === "terminal" && <TerminalPanel />}
        {view === "files" && <FilesPanel canUpload={control !== null} />}
      </div>
    </section>
  );
}

function DockError({ screen }: { screen: Screen }) {
  const { error } = screen;
  if (error === null) return null;
  return (
    <div role="alert" className="flex items-center gap-3 border-b border-danger/30 bg-danger-soft px-4 py-2 text-sm text-danger">
      <p className="min-w-0 flex-1 break-words">{error.message}</p>
      <button
        type="button"
        onClick={() => void screen.change(error.retry)}
        className="h-8 shrink-0 rounded-lg border border-danger/40 px-3 text-xs font-medium transition hover:bg-danger/10"
      >
        Retry
      </button>
    </div>
  );
}

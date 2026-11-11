"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { FilesPanel } from "@/components/computer/FilesPanel";
import { PhonePanel } from "@/components/computer/PhonePanel";
import { BUTTON, ScreenControls, ScreenNotices } from "@/components/computer/ScreenControls";
import { COMPUTER_SCREEN } from "@/components/computer/server";
import { useScreen } from "@/components/computer/useScreen";

const TerminalPanel = dynamic(
  () => import("@/components/computer/TerminalPanel").then((m) => m.TerminalPanel),
  { ssr: false },
);

type Panel = "terminal" | "files";

/** The shared computer's screen and the bots' phone, live: viewed, or controlled by the person for a while. */
export default function ComputerPage() {
  const screen = useScreen(COMPUTER_SCREEN, "control");
  const [panel, setPanel] = useState<Panel | null>(null);
  const { control } = screen;

  useEffect(() => {
    if (control === null) setPanel((open) => (open === "terminal" ? null : open));
  }, [control]);

  const toggle = (chosen: Panel) => setPanel((open) => (open === chosen ? null : chosen));

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
          <ScreenControls
            screen={screen}
            takeTitle="Use your own mouse, keyboard and paste on the computer"
            releaseTitle="Hand the screen back to the bots"
          />
        </div>
      </header>

      <ScreenNotices screen={screen} />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {screen.url === null ? (
            screen.busy && <p className="px-6 py-6 text-sm text-ink-soft">Starting the computer…</p>
          ) : (
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
        <PhonePanel />
        {panel !== null && (
          <aside className="flex min-h-0 w-[36rem] max-w-[50%] shrink-0 flex-col border-l border-line">
            {panel === "terminal" ? <TerminalPanel /> : <FilesPanel canUpload={control !== null} />}
          </aside>
        )}
      </div>
    </>
  );
}

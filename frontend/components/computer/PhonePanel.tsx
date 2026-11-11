"use client";

import { useEffect, useState } from "react";

import { ScreenControls, ScreenNotices } from "@/components/computer/ScreenControls";
import { PHONE_SCREEN } from "@/components/computer/server";
import { useScreen } from "@/components/computer/useScreen";
import { listMcpServers, type McpServer } from "@/lib/mcpServers";

/** Whether the bots' phone can be shown: still asking, never added, added but off, or on. */
type PhoneState = "checking" | "not-set-up" | "unavailable" | "connected";

const SAID: Record<"not-set-up" | "unavailable", string> = {
  "not-set-up": "The phone is not set up.",
  unavailable: "The phone is not available right now.",
};

function stateOf(servers: McpServer[]): PhoneState {
  const phone = servers.find((server) => server.id === PHONE_SCREEN.id);
  if (phone === undefined) return "not-set-up";
  return phone.status === "connected" ? "connected" : "unavailable";
}

function usePhoneState(): PhoneState {
  const [state, setState] = useState<PhoneState>("checking");
  useEffect(() => {
    let cancelled = false;
    listMcpServers()
      .then(({ servers }) => {
        if (!cancelled) setState(stateOf(servers));
      })
      .catch(() => {
        if (!cancelled) setState("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return state;
}

function PhoneScreen() {
  const screen = useScreen(PHONE_SCREEN, "view");
  return (
    <>
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2">
        <h2 className="text-sm font-medium">Phone</h2>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <ScreenControls
            screen={screen}
            takeTitle="Use your own mouse and keyboard on the phone"
            releaseTitle="Hand the phone back to the bots"
          />
        </div>
      </div>
      <ScreenNotices screen={screen} />
      <div className="min-h-0 flex-1 overflow-auto">
        {screen.url === null ? (
          screen.busy && <p className="px-4 py-4 text-sm text-ink-soft">Starting the phone…</p>
        ) : (
          <iframe
            key={screen.url}
            src={screen.url}
            title="The phone's screen"
            sandbox="allow-scripts allow-pointer-lock"
            allow="clipboard-read; clipboard-write"
            className="block aspect-[9/16] w-full border-0"
          />
        )}
      </div>
    </>
  );
}

/** The bots' phone beside the computer's screen, or a line saying why it cannot be shown. */
export function PhonePanel() {
  const state = usePhoneState();
  return (
    <aside className="flex min-h-0 w-80 max-w-[40%] shrink-0 flex-col border-l border-line">
      {state === "connected" ? (
        <PhoneScreen />
      ) : (
        state !== "checking" && <p className="px-4 py-4 text-sm text-ink-soft">{SAID[state]}</p>
      )}
    </aside>
  );
}

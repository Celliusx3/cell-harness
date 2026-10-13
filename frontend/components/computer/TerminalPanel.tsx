"use client";

import "@xterm/xterm/css/xterm.css";

import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import { useEffect, useRef, useState } from "react";

import { inputFrame, openTerminal, resizeFrame, socketUrl } from "@/components/computer/terminal";

const CLOSED = "\r\n\x1b[2m[closed]\x1b[0m\r\n";
const FONT = "ui-monospace, SFMono-Regular, Menlo, monospace";

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : "The shell could not be opened.";
}

/** A shell on the computer for the person holding control, until the panel closes. */
export function TerminalPanel() {
  const host = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const element = host.current;
    if (element === null) return;
    const terminal = new Terminal({ cursorBlink: true, fontFamily: FONT, fontSize: 13 });
    const fit = new FitAddon();
    terminal.loadAddon(fit);
    terminal.open(element);
    let socket: WebSocket | null = null;
    let cancelled = false;
    const send = (frame: Uint8Array<ArrayBuffer>) => {
      if (socket?.readyState === WebSocket.OPEN) socket.send(frame);
    };
    const refit = () => {
      fit.fit();
      send(resizeFrame(terminal.cols, terminal.rows));
    };
    refit();
    const typing = terminal.onData((data) => send(inputFrame(data)));
    const observer = new ResizeObserver(refit);
    observer.observe(element);
    openTerminal()
      .then((relayUrl) => {
        if (cancelled) return;
        const connection = new WebSocket(socketUrl(relayUrl, window.location), ["binary"]);
        connection.binaryType = "arraybuffer";
        connection.onopen = () => {
          refit();
          terminal.focus();
        };
        connection.onmessage = (event: MessageEvent<unknown>) => {
          if (event.data instanceof ArrayBuffer) terminal.write(new Uint8Array(event.data));
          else if (typeof event.data === "string") terminal.write(event.data);
        };
        connection.onclose = () => {
          if (!cancelled) terminal.write(CLOSED);
        };
        socket = connection;
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(messageOf(err));
      });
    return () => {
      cancelled = true;
      observer.disconnect();
      typing.dispose();
      socket?.close();
      terminal.dispose();
    };
  }, []);

  return (
    <section aria-label="Terminal" className="flex min-h-0 flex-1 flex-col bg-black">
      {error !== null && (
        <p role="alert" className="bg-danger-soft px-3 py-2 text-sm break-words text-danger">
          {error}
        </p>
      )}
      <div ref={host} className="min-h-0 flex-1 px-2 py-1.5" />
    </section>
  );
}

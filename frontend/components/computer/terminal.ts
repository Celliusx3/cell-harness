import { z } from "zod";

import { parsedResult, PREVIEW_URI, RELAY_META, RelayMeta, SERVER } from "@/components/computer/server";
import { callAppTool } from "@/lib/api";

const INPUT = 0;
const RESIZE = 1;
const HEADER_BYTES = 5;
const LARGEST_SIDE = 1000;

const Opened = z.object({ _meta: RelayMeta });

function frame(kind: number, payload: Uint8Array): Uint8Array<ArrayBuffer> {
  const bytes = new Uint8Array(new ArrayBuffer(HEADER_BYTES + payload.length));
  const view = new DataView(bytes.buffer);
  view.setUint8(0, kind);
  view.setUint32(1, payload.length);
  bytes.set(payload, HEADER_BYTES);
  return bytes;
}

function clampedSide(cells: number): number {
  return Math.min(LARGEST_SIDE, Math.max(1, Math.round(cells) || 1));
}

export function inputFrame(text: string): Uint8Array<ArrayBuffer> {
  return frame(INPUT, new TextEncoder().encode(text));
}

export function resizeFrame(cols: number, rows: number): Uint8Array<ArrayBuffer> {
  const payload = new Uint8Array(new ArrayBuffer(4));
  const view = new DataView(payload.buffer);
  view.setUint16(0, clampedSide(cols));
  view.setUint16(2, clampedSide(rows));
  return frame(RESIZE, payload);
}

export function socketUrl(relayUrl: string, page: { protocol: string; host: string }): string {
  return `${page.protocol === "https:" ? "wss:" : "ws:"}//${page.host}${relayUrl}`;
}

/** A new shell on the computer, refused unless the person holds control: its relay url. */
export async function openTerminal(): Promise<string> {
  const result = await callAppTool(SERVER, "terminal_session", {}, PREVIEW_URI);
  return parsedResult(Opened, result)._meta[RELAY_META].url;
}

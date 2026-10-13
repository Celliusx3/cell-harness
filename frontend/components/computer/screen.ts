import { z } from "zod";

import {
  parsedResult,
  PREVIEW_URI,
  RELAY_META,
  RelayMeta,
  SERVER,
  throwIfFailed,
} from "@/components/computer/server";
import { callAppTool } from "@/lib/api";

const Viewed = z.object({
  structuredContent: z.object({ mode: z.literal("view"), held_until: z.null() }),
});
const ViewedWithLink = Viewed.extend({ _meta: RelayMeta });
const Controlled = z.object({
  structuredContent: z.object({
    mode: z.literal("control"),
    held_until: z.iso.datetime({ offset: true }),
  }),
  _meta: RelayMeta,
});

/** The person's control of the screen: the page that takes their input, until when. */
export interface Control {
  url: string;
  until: Date;
}

/** The relay page that shows the screen, view-only, starting the computer if it is stopped. */
export async function viewScreen(): Promise<string> {
  const result = await callAppTool(SERVER, "screen_session", { mode: "view" }, PREVIEW_URI);
  return parsedResult(ViewedWithLink, result)._meta[RELAY_META].url;
}

/** Control of the screen for the person; the bots' browser waits until it is released. */
export async function takeControl(): Promise<Control> {
  const result = await callAppTool(SERVER, "screen_session", { mode: "control" }, PREVIEW_URI);
  const controlled = parsedResult(Controlled, result);
  return {
    url: controlled._meta[RELAY_META].url,
    until: new Date(controlled.structuredContent.held_until),
  };
}

export async function keepAwake(): Promise<void> {
  throwIfFailed(await callAppTool(SERVER, "keep_awake", {}, PREVIEW_URI));
}

/** The screen handed back to the bots. */
export async function releaseControl(): Promise<void> {
  parsedResult(Viewed, await callAppTool(SERVER, "release_control", {}, PREVIEW_URI));
}

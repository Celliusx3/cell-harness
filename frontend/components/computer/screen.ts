import { z } from "zod";

import {
  parsedResult,
  RELAY_META,
  RelayMeta,
  type ScreenServer,
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

/** A screen opened to watch: its page, and the person's control when they still hold it. */
export interface Opened {
  url: string;
  control: Control | null;
}

function controlOf(controlled: z.infer<typeof Controlled>): Control {
  return {
    url: controlled._meta[RELAY_META].url,
    until: new Date(controlled.structuredContent.held_until),
  };
}

/** The relay page that shows the screen, starting the machine if it is stopped; a hold comes back as control. */
export async function viewScreen(server: ScreenServer): Promise<Opened> {
  const result = await callAppTool(server.id, "screen_session", { mode: "view" }, server.previewUri);
  const held = Controlled.safeParse(result);
  if (held.success) {
    const control = controlOf(held.data);
    return { url: control.url, control };
  }
  return { url: parsedResult(ViewedWithLink, result)._meta[RELAY_META].url, control: null };
}

/** Control of the screen for the person; the bots wait until it is released. */
export async function takeControl(server: ScreenServer): Promise<Control> {
  const result = await callAppTool(
    server.id,
    "screen_session",
    { mode: "control" },
    server.previewUri,
  );
  return controlOf(parsedResult(Controlled, result));
}

export async function keepAwake(server: ScreenServer): Promise<void> {
  throwIfFailed(await callAppTool(server.id, "keep_awake", {}, server.previewUri));
}

/** The screen handed back to the bots. */
export async function releaseControl(server: ScreenServer): Promise<void> {
  const result = await callAppTool(server.id, "release_control", {}, server.previewUri);
  parsedResult(Viewed, result);
}

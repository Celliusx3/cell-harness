import assert from "node:assert/strict";
import { test } from "node:test";

import { trayMenuItems } from "./trayMenu";

const NOTHING = (): void => undefined;

test("the menu opens the chat, the credentials, the browser and the file, then quits", () => {
  const labels = trayMenuItems({
    showChatWindow: NOTHING,
    showCredentials: NOTHING,
    openInBrowser: NOTHING,
    showSettingsFile: NOTHING,
    quit: NOTHING,
  }).map((item) => item.label ?? item.type);

  assert.deepEqual(labels, [
    "Open Cell Harness",
    "Credentials…",
    "Open in Browser",
    "Show Settings File",
    "separator",
    "Quit Cell Harness",
  ]);
});

test("Credentials… shows the credentials", () => {
  let shown = 0;
  const credentials = trayMenuItems({
    showChatWindow: NOTHING,
    showCredentials: () => {
      shown += 1;
    },
    openInBrowser: NOTHING,
    showSettingsFile: NOTHING,
    quit: NOTHING,
  }).find((item) => item.label === "Credentials…");

  (credentials?.click as (() => void) | undefined)?.();

  assert.equal(shown, 1);
});

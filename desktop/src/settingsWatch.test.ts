import assert from "node:assert/strict";
import { mkdtempSync, renameSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";
import { setTimeout as delay } from "node:timers/promises";

import { isSettingsChange, watchSettings } from "./settingsWatch";

const FILE = "/d/config.local.json";
const NOTICE_WITHIN_MS = 5000;
const POLL_MS = 50;
const NO_SECOND_CHANGE_MS = 1000;

test("a change to the settings file is one", () => {
  assert.equal(isSettingsChange("config.local.json", FILE), true);
});

test("the temp file a save writes first, another file, or no name is not", () => {
  assert.equal(isSettingsChange(".config.local.json.k2j1.tmp", FILE), false);
  assert.equal(isSettingsChange("harness.pid", FILE), false);
  assert.equal(isSettingsChange(null, FILE), false);
});

test("replacing the file the way a save does is noticed once", async () => {
  const folder = mkdtempSync(path.join(tmpdir(), "watch-"));
  const file = path.join(folder, "config.local.json");
  writeFileSync(file, "{}");
  let changes = 0;
  const stop = watchSettings(file, () => {
    changes += 1;
  });

  const temp = path.join(folder, ".config.local.json.abc.tmp");
  writeFileSync(temp, '{"telegram": {"bot_token": "t"}}');
  renameSync(temp, file);
  const deadline = Date.now() + NOTICE_WITHIN_MS;
  while (changes === 0 && Date.now() < deadline) await delay(POLL_MS);
  await delay(NO_SECOND_CHANGE_MS);
  stop();

  assert.equal(changes, 1);
});

import assert from "node:assert/strict";
import { mkdtempSync, readdirSync, readFileSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import {
  newEncryptionKey,
  parseLocalSettings,
  readLocalSettings,
  withEncryptionKey,
  writeLocalSettings,
} from "./localSettings";

const NO_KEY_EXPECTED = (): string => assert.fail("a new encryption key was made");

test("a settings file that is not JSON is refused, naming the file", () => {
  assert.throws(() => parseLocalSettings("{nope", "/d/config.local.json"), /\/d\/config\.local\.json is not valid JSON/);
});

test("a settings file that is not a JSON object is refused", () => {
  assert.throws(() => parseLocalSettings("[]", "/d/config.local.json"), /\/d\/config\.local\.json/);
});

test("no settings file yet gains one holding only a new encryption key", () => {
  assert.deepEqual(withEncryptionKey(null, () => "k-new"), { secrets: { encryption_key: "k-new" } });
});

test("a settings file with no encryption key gains one, and keeps every other value", () => {
  const settings = { telegram: { bot_token: "t-1" }, secrets: { path: "/s.json" } };

  assert.deepEqual(withEncryptionKey(settings, () => "k-new"), {
    telegram: { bot_token: "t-1" },
    secrets: { path: "/s.json", encryption_key: "k-new" },
  });
});

test("a blank encryption key is replaced, since the harness cannot start with one", () => {
  assert.deepEqual(withEncryptionKey({ secrets: { encryption_key: " " } }, () => "k-new"), {
    secrets: { encryption_key: "k-new" },
  });
});

test("an encryption key is never replaced, or saved keys become unreadable", () => {
  const settings = { secrets: { encryption_key: "k-old" } };

  assert.equal(withEncryptionKey(settings, NO_KEY_EXPECTED), settings);
});

test("the file is written readable by its owner only, with no temp file left", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "local-settings-"));
  const file = path.join(folder, "config.local.json");

  writeLocalSettings(file, { secrets: { encryption_key: "k-1" } });

  assert.equal(statSync(file).mode & 0o777, 0o600);
  assert.deepEqual(JSON.parse(readFileSync(file, "utf8")), { secrets: { encryption_key: "k-1" } });
  assert.deepEqual(readdirSync(folder), ["config.local.json"]);
});

test("reading a settings file that does not exist gives no settings", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "local-settings-"));

  assert.equal(readLocalSettings(path.join(folder, "config.local.json")), null);
});

test("reading a settings file gives what was written", () => {
  const file = path.join(mkdtempSync(path.join(tmpdir(), "local-settings-")), "config.local.json");
  writeLocalSettings(file, { telegram: { bot_token: "t-1" } });

  assert.deepEqual(readLocalSettings(file), { telegram: { bot_token: "t-1" } });
});

test("a new encryption key is 32 random bytes as hex, different each time", () => {
  const first = newEncryptionKey();

  assert.match(first, /^[0-9a-f]{64}$/);
  assert.notEqual(newEncryptionKey(), first);
});

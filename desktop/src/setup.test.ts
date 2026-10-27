import assert from "node:assert/strict";
import { mkdtempSync, readdirSync, readFileSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import {
  checkAnswers,
  committedEndpoint,
  formDefaults,
  needsSetup,
  newEncryptionKey,
  parseLocalSettings,
  readLocalSettings,
  withSetup,
  writeLocalSettings,
} from "./setup";

const COMMITTED = { baseUrl: "https://api.ilmu.ai/v1", model: "glm-5.3-flashx" };
const ANSWERS = { apiKey: "sk-new", ...COMMITTED };
const NO_KEY_EXPECTED = (): string => assert.fail("a new encryption key was made");

test("a missing settings file needs setup", () => {
  assert.equal(needsSetup(null), true);
});

test("a settings file with no API key, or a blank one, needs setup", () => {
  assert.equal(needsSetup({}), true);
  assert.equal(needsSetup({ llm: { api_key: "   " } }), true);
});

test("a settings file with an API key needs no setup", () => {
  assert.equal(needsSetup({ llm: { api_key: "sk-x" } }), false);
});

test("a settings file that is not JSON is refused, naming the file", () => {
  assert.throws(() => parseLocalSettings("{nope", "/d/config.local.json"), /\/d\/config\.local\.json is not valid JSON/);
});

test("a settings file that is not a JSON object is refused", () => {
  assert.throws(() => parseLocalSettings("[]", "/d/config.local.json"), /\/d\/config\.local\.json/);
});

test("setup keeps every value it does not set, such as a Telegram token", () => {
  const saved = withSetup({ telegram: { bot_token: "t-1" }, llm: { api_key: "", vision: false } }, ANSWERS, COMMITTED, () => "k");

  assert.deepEqual(saved.telegram, { bot_token: "t-1" });
  assert.equal((saved.llm as Record<string, unknown>).api_key, "sk-new");
  assert.equal((saved.llm as Record<string, unknown>).vision, false);
});

test("setup makes an encryption key when there is none", () => {
  const saved = withSetup(null, ANSWERS, COMMITTED, () => "k-new");

  assert.deepEqual(saved.secrets, { encryption_key: "k-new" });
});

test("setup never replaces an encryption key, or saved keys become unreadable", () => {
  const saved = withSetup({ secrets: { encryption_key: "k-old" } }, ANSWERS, COMMITTED, NO_KEY_EXPECTED);

  assert.deepEqual(saved.secrets, { encryption_key: "k-old" });
});

test("an endpoint and model equal to the app's own are not copied into the file", () => {
  const saved = withSetup({ llm: { base_url: "http://old", model: "old" } }, ANSWERS, COMMITTED, () => "k");

  assert.deepEqual(saved.llm, { api_key: "sk-new" });
});

test("an endpoint or model the friend changed is saved in the file", () => {
  const saved = withSetup(null, { ...ANSWERS, baseUrl: "http://localhost:1234/v1", model: "qwen" }, COMMITTED, () => "k");

  assert.deepEqual(saved.llm, { api_key: "sk-new", base_url: "http://localhost:1234/v1", model: "qwen" });
});

test("the form starts from the file's endpoint and model, then the app's own", () => {
  assert.deepEqual(formDefaults(null, COMMITTED), COMMITTED);
  assert.deepEqual(formDefaults({ llm: { model: "qwen" } }, COMMITTED), { ...COMMITTED, model: "qwen" });
});

test("the form's answers are trimmed", () => {
  assert.deepEqual(checkAnswers({ apiKey: " sk-1 ", baseUrl: " https://a.b/v1 ", model: " m " }), {
    apiKey: "sk-1",
    baseUrl: "https://a.b/v1",
    model: "m",
  });
});

test("a blank key, an endpoint that is not http, or a blank model is refused", () => {
  assert.throws(() => checkAnswers({ ...ANSWERS, apiKey: " " }), /API key/);
  assert.throws(() => checkAnswers({ ...ANSWERS, baseUrl: "ftp://x" }), /endpoint/);
  assert.throws(() => checkAnswers({ ...ANSWERS, model: "" }), /model/);
  assert.throws(() => checkAnswers("sk-1"), /API key/);
});

test("the file is written readable by its owner only, with no temp file left", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "setup-"));
  const file = path.join(folder, "config.local.json");

  writeLocalSettings(file, { llm: { api_key: "sk-1" } });

  assert.equal(statSync(file).mode & 0o777, 0o600);
  assert.deepEqual(JSON.parse(readFileSync(file, "utf8")), { llm: { api_key: "sk-1" } });
  assert.deepEqual(readdirSync(folder), ["config.local.json"]);
});

test("reading a settings file that does not exist gives no settings", () => {
  const folder = mkdtempSync(path.join(tmpdir(), "setup-"));

  assert.equal(readLocalSettings(path.join(folder, "config.local.json")), null);
});

test("reading a settings file gives what was written", () => {
  const file = path.join(mkdtempSync(path.join(tmpdir(), "setup-")), "config.local.json");
  writeLocalSettings(file, { telegram: { bot_token: "t-1" } });

  assert.deepEqual(readLocalSettings(file), { telegram: { bot_token: "t-1" } });
});

test("the app's own endpoint and model come from its committed settings", () => {
  const configJson = readFileSync(path.resolve(__dirname, "..", "config.json"), "utf8");

  assert.deepEqual(committedEndpoint(configJson), COMMITTED);
});

test("committed settings with no model are refused", () => {
  assert.throws(() => committedEndpoint('{"llm": {"base_url": "https://a.b/v1"}}'), /llm\.model/);
});

test("a new encryption key is 32 random bytes as hex, different each time", () => {
  const first = newEncryptionKey();

  assert.match(first, /^[0-9a-f]{64}$/);
  assert.notEqual(newEncryptionKey(), first);
});

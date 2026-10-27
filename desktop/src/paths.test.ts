import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";

import { APP_NAME, checkoutLayout, dataFiles, HARNESS_PORT, userDataFolder } from "./paths";

const DESKTOP = path.resolve(__dirname, "..");
const REPO = path.resolve(DESKTOP, "..");
const HOME = "/Users/sam";

const DATA_PATHS = [
  ["sessions", "root"],
  ["skills", "editable"],
  ["approval", "grants_path"],
  ["bots", "path"],
  ["secrets", "path"],
  ["files", "root"],
] as const;

function appSettings(): Record<string, Record<string, unknown>> {
  return JSON.parse(readFileSync(path.join(DESKTOP, "config.json"), "utf8"));
}

test("the data folder is the app's own, under Application Support", () => {
  assert.equal(userDataFolder(HOME), "/Users/sam/Library/Application Support/Cell Harness");
});

test("the product name is the data folder's name", () => {
  const manifest = JSON.parse(readFileSync(path.join(DESKTOP, "package.json"), "utf8"));
  assert.equal(manifest.productName, APP_NAME);
});

test("every data path in the app's settings is in the data folder", () => {
  const settings = appSettings();
  const folder = userDataFolder(HOME) + path.sep;
  for (const [section, key] of DATA_PATHS) {
    const value = String(settings[section][key]).replace(/^~\//, `${HOME}/`);
    assert.ok(value.startsWith(folder), `${section}.${key} is ${value}`);
  }
});

test("the friend's settings file, the logs and the harness's pid file are in the data folder", () => {
  const files = dataFiles("/d");
  assert.equal(files.localJson, "/d/config.local.json");
  assert.equal(files.harnessLog, "/d/logs/harness.log");
  assert.equal(files.pagesLog, "/d/logs/pages.log");
  assert.equal(files.pidFile, "/d/harness.pid");
});

test("on the checkout, the harness runs through uv from the backend folder", () => {
  const layout = checkoutLayout(REPO);
  assert.deepEqual(layout.python, { command: "uv", args: ["run", "--quiet", "python"] });
  assert.equal(layout.backendDir, path.join(REPO, "backend"));
  assert.equal(layout.configJson, path.join(REPO, "desktop", "config.json"));
  assert.equal(layout.pagesServer, path.join(REPO, "desktop", "build", "pages", "server.js"));
  assert.deepEqual(layout.extraPath, []);
  assert.deepEqual(layout.pythonPath, []);
});

test("the pages are built to call the harness on its port", () => {
  const script = readFileSync(path.join(DESKTOP, "scripts", "build-pages.sh"), "utf8");
  assert.ok(script.includes(`BACKEND_PORT=${HARNESS_PORT}`));
});

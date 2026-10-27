import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";

import { APP_NAME, checkoutLayout, dataFiles, HARNESS_PORT, packagedLayout, userDataFolder } from "./paths";

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
  assert.deepEqual(layout.harnessEnv, {});
});

test("the pages are built to call the harness on its port", () => {
  const script = readFileSync(path.join(DESKTOP, "scripts", "build-pages.sh"), "utf8");
  assert.ok(script.includes(`BACKEND_PORT=${HARNESS_PORT}`));
});

test("in the packaged app, the harness runs on the app's own Python, with Deno on its PATH", () => {
  const layout = packagedLayout("/Applications/Cell Harness.app/Contents/Resources");
  const resources = "/Applications/Cell Harness.app/Contents/Resources";

  assert.deepEqual(layout.python, { command: `${resources}/python/bin/python3`, args: [] });
  assert.equal(layout.backendDir, `${resources}/app/backend`);
  assert.equal(layout.configJson, `${resources}/app/desktop/config.json`);
  assert.equal(layout.pagesServer, `${resources}/pages/server.js`);
  assert.deepEqual(layout.extraPath, [`${resources}/bin`]);
  assert.deepEqual(layout.pythonPath, [`${resources}/app/backend`, `${resources}/site-packages`]);
  assert.deepEqual(layout.harnessEnv, { PYTHONDONTWRITEBYTECODE: "1" });
});

test("the bundle puts each program where the packaged layout looks for it", () => {
  const script = readFileSync(path.join(DESKTOP, "scripts", "bundle.sh"), "utf8");
  assert.ok(script.includes("compileall --invalidation-mode unchecked-hash"), "bundle.sh never compiles the bytecode");
  for (const folder of ["python", "site-packages", "bin", "app/backend", "app/desktop", "app/.agents/skills/create-skill", "pages"]) {
    assert.ok(script.includes(`$BUNDLE/${folder}`), `bundle.sh never fills ${folder}`);
  }
});

test("electron-builder copies the whole bundle into Resources", () => {
  const manifest = JSON.parse(readFileSync(path.join(DESKTOP, "package.json"), "utf8"));
  assert.deepEqual(manifest.build.extraResources, [{ from: "build/bundle", to: ".", filter: ["**/*"] }]);
  assert.equal(manifest.build.mac.identity, "-");
  assert.deepEqual(manifest.build.mac.target, [{ target: "dmg", arch: ["arm64"] }]);
});

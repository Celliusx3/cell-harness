import assert from "node:assert/strict";
import { createServer, type AddressInfo } from "node:net";
import path from "node:path";
import { test } from "node:test";

import { checkoutLayout, dataFiles } from "./paths";
import { firstPortInUse, harnessSpec, pagesSpec, waitForPort } from "./processes";

const REPO = path.resolve(__dirname, "..", "..");
const NEVER = new Promise<never>(() => undefined);

test("the harness listens on this Mac only, on its port, with both settings files", () => {
  const spec = harnessSpec(checkoutLayout(REPO), dataFiles("/d"), {
    PATH: "/usr/bin",
    HOME: "/Users/sam",
  });

  assert.equal(spec.command, "uv");
  assert.deepEqual(spec.args, [
    "run",
    "--quiet",
    "python",
    "-m",
    "uvicorn",
    "harness.web.server:create_web_app",
    "--factory",
    "--host",
    "127.0.0.1",
    "--port",
    "4886",
  ]);
  assert.equal(spec.cwd, path.join(REPO, "backend"));
  assert.equal(spec.env.HARNESS_CONFIG, path.join(REPO, "desktop", "config.json"));
  assert.equal(spec.env.HARNESS_CONFIG_LOCAL, "/d/config.local.json");
  assert.equal(spec.env.HOME, "/Users/sam");
  assert.equal(spec.env.PATH, "/usr/bin");
});

test("a setting in the shell that started the app never reaches the harness", () => {
  const spec = harnessSpec(checkoutLayout(REPO), dataFiles("/d"), {
    PATH: "/usr/bin",
    HARNESS_LLM__API_KEY: "sk-from-the-shell",
  });

  assert.equal(spec.env.HARNESS_LLM__API_KEY, undefined);
});

test("a lowercase setting is dropped too, since the harness reads settings in any case", () => {
  const spec = harnessSpec(checkoutLayout(REPO), dataFiles("/d"), {
    PATH: "/usr/bin",
    harness_llm__api_key: "sk-from-the-shell",
  });

  assert.equal(spec.env.harness_llm__api_key, undefined);
});

test("the layout's own programs come first on the harness's PATH", () => {
  const layout = { ...checkoutLayout(REPO), extraPath: ["/app/bin"], pythonPath: ["/a", "/b"] };

  const spec = harnessSpec(layout, dataFiles("/d"), { PATH: "/usr/bin" });

  assert.equal(spec.env.PATH, "/app/bin:/usr/bin");
  assert.equal(spec.env.PYTHONPATH, "/a:/b");
});

test("the page server listens on this Mac only, on its port", () => {
  const spec = pagesSpec(checkoutLayout(REPO), { PATH: "/usr/bin", HARNESS_X: "y" });

  assert.equal(spec.modulePath, path.join(REPO, "desktop", "build", "pages", "server.js"));
  assert.equal(spec.cwd, path.join(REPO, "desktop", "build", "pages"));
  assert.equal(spec.env.PORT, "4887");
  assert.equal(spec.env.HOSTNAME, "127.0.0.1");
  assert.equal(spec.env.HARNESS_X, undefined);
});

test("waiting for a port ends once something listens on it", async () => {
  const server = createServer().listen(0, "127.0.0.1");
  await new Promise((resolve) => server.once("listening", resolve));
  const { port } = server.address() as AddressInfo;

  await waitForPort({ host: "127.0.0.1", port }, 2000, NEVER);

  server.close();
});

test("waiting for a port fails when the program exits first", async () => {
  await assert.rejects(waitForPort({ host: "127.0.0.1", port: 9 }, 5000, Promise.resolve(1)), /exited/);
});

test("waiting for a port fails when nothing listens in time", async () => {
  await assert.rejects(waitForPort({ host: "127.0.0.1", port: 9 }, 300, NEVER), /did not answer/);
});

test("the first port another program holds is named, and none when all are free", async () => {
  const server = createServer().listen(0, "127.0.0.1");
  await new Promise((resolve) => server.once("listening", resolve));
  const { port } = server.address() as AddressInfo;

  assert.equal(await firstPortInUse("127.0.0.1", [9, port]), port);
  server.close();
  await new Promise((resolve) => server.once("close", resolve));
  assert.equal(await firstPortInUse("127.0.0.1", [9, port]), null);
});

test("the layout's own settings for Python reach the harness, after the parent's", () => {
  const layout = { ...checkoutLayout(REPO), harnessEnv: { PYTHONDONTWRITEBYTECODE: "1" } };

  const spec = harnessSpec(layout, dataFiles("/d"), { PATH: "/usr/bin", PYTHONDONTWRITEBYTECODE: "" });

  assert.equal(spec.env.PYTHONDONTWRITEBYTECODE, "1");
});

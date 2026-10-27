import assert from "node:assert/strict";
import { test } from "node:test";

import { HARNESS_PORT } from "./paths";
import { HARNESS_APP_FACTORY } from "./processes";
import { isOurHarness, parsePidFile, pidFileText, portInUseReason } from "./strays";

const OURS = `/x/python3 -m uvicorn ${HARNESS_APP_FACTORY} --factory --host 127.0.0.1 --port ${HARNESS_PORT}`;

test("the pid file holds the harness's pid, and reads back the same", () => {
  assert.deepEqual(parsePidFile(pidFileText(4242)), { harnessPid: 4242 });
});

test("a pid file that is not ours holds no pid to stop", () => {
  assert.equal(parsePidFile("{nope"), null);
  assert.equal(parsePidFile('{"harnessPid": "4242"}'), null);
  assert.equal(parsePidFile('{"harnessPid": -1}'), null);
  assert.equal(parsePidFile("[]"), null);
});

test("a dead pid is not stopped", () => {
  assert.equal(isOurHarness(null), false);
});

test("a live pid that runs another program is not stopped", () => {
  assert.equal(isOurHarness("/Applications/Safari.app/Contents/MacOS/Safari"), false);
});

test("a live pid that runs a harness on another port is not stopped", () => {
  assert.equal(isOurHarness(`python -m uvicorn ${HARNESS_APP_FACTORY} --factory --port 4896`), false);
});

test("a live pid that runs our harness on our port is stopped", () => {
  assert.equal(isOurHarness(OURS), true);
});

test("a port in use names the port and says what to do", () => {
  assert.match(portInUseReason(4887), /4887 is in use/);
  assert.match(portInUseReason(4887), /quit it/i);
});

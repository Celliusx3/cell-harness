import assert from "node:assert/strict";
import { test } from "node:test";

import {
  harnessBasePath,
  LOGIN_SHELL_TIMEOUT_MS,
  loginShell,
  loginShellArgs,
  parseMarkedPath,
  PATH_END_MARKER,
  PATH_START_MARKER,
  runShell,
  type ShellRunner,
} from "./loginPath";

const marked = (pathText: string): string => `${PATH_START_MARKER}${pathText}${PATH_END_MARKER}`;

test("the user's shell is used when SHELL is an absolute path", () => {
  assert.equal(loginShell("/opt/homebrew/bin/fish"), "/opt/homebrew/bin/fish");
});

test("zsh is used when SHELL is unset or not an absolute path", () => {
  assert.equal(loginShell(undefined), "/bin/zsh");
  assert.equal(loginShell(""), "/bin/zsh");
  assert.equal(loginShell("zsh"), "/bin/zsh");
});

test("the shell is run as a login, interactive shell that prints PATH between the markers", () => {
  const args = loginShellArgs();

  assert.deepEqual(args.slice(0, 3), ["-l", "-i", "-c"]);
  assert.equal(args[3], `printf '%s%s%s' '${PATH_START_MARKER}' "$PATH" '${PATH_END_MARKER}'`);
});

test("the PATH between the markers is read, whatever the profile printed around it", () => {
  const output = `Welcome back!\n${marked("/opt/homebrew/bin:/usr/bin")}\nlast login`;

  assert.equal(parseMarkedPath(output), "/opt/homebrew/bin:/usr/bin");
});

test("output with no markers, or only the start marker, is refused", () => {
  assert.throws(() => parseMarkedPath("/usr/bin:/bin"), /no PATH markers/);
  assert.throws(() => parseMarkedPath(`${PATH_START_MARKER}/usr/bin`), /no PATH markers/);
  assert.throws(() => parseMarkedPath(`${PATH_END_MARKER}/usr/bin${PATH_START_MARKER}`), /no PATH markers/);
});

test("an empty PATH between the markers is refused", () => {
  assert.throws(() => parseMarkedPath(marked("  \n")), /empty PATH/);
});

test("the login shell's PATH is the base PATH when the shell answers", async () => {
  const calls: Array<readonly [string, readonly string[], number]> = [];
  const run: ShellRunner = async (shell, args, timeoutMs) => {
    calls.push([shell, args, timeoutMs]);
    return marked("/opt/homebrew/bin:/usr/bin");
  };

  const base = await harnessBasePath({ SHELL: "/bin/bash", PATH: "/usr/bin:/bin" }, run);

  assert.deepEqual(base, { source: "login-shell", path: "/opt/homebrew/bin:/usr/bin" });
  assert.deepEqual(calls, [["/bin/bash", loginShellArgs(), LOGIN_SHELL_TIMEOUT_MS]]);
});

test("a failing shell keeps the inherited PATH and says why", async () => {
  const run: ShellRunner = async () => {
    throw new Error("exited with 127");
  };

  const base = await harnessBasePath({ PATH: "/usr/bin:/bin" }, run);

  assert.deepEqual(base, { source: "inherited", path: "/usr/bin:/bin", reason: "/bin/zsh: exited with 127" });
});

test("a shell that prints no markers keeps the inherited PATH and says why", async () => {
  const base = await harnessBasePath({ SHELL: "/bin/sh", PATH: "/usr/bin" }, async () => "hello");

  assert.equal(base.source, "inherited");
  assert.equal(base.path, "/usr/bin");
  assert.match(base.source === "inherited" ? base.reason : "", /^\/bin\/sh: .*no PATH markers/);
});

test("running a program resolves with what it printed", async () => {
  assert.equal(await runShell("/bin/sh", ["-c", "printf hi"], 2000), "hi");
});

test("running a program fails when it exits with an error", async () => {
  await assert.rejects(runShell("/bin/sh", ["-c", "exit 3"], 2000), /exited with 3/);
});

test("running a program fails when it is not there", async () => {
  await assert.rejects(runShell("/no/such/shell", [], 2000), /ENOENT/);
});

test("running a program fails, and kills it, when it outlasts the time limit", async () => {
  const started = Date.now();

  await assert.rejects(runShell("/bin/sh", ["-c", "trap '' TERM; sleep 10"], 200), /no answer within 200 ms/);
  assert.ok(Date.now() - started < 2000);
});

test("a program reads nothing from stdin, so a prompt in a profile cannot hang it", async () => {
  assert.equal(await runShell("/bin/sh", ["-c", "cat; printf done"], 2000), "done");
});

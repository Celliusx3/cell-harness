import { execFile, spawn, type ChildProcess } from "node:child_process";
import { appendFileSync, closeSync, createWriteStream, openSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { setTimeout as delay } from "node:timers/promises";
import { promisify } from "node:util";

import { utilityProcess } from "electron";

import type { ChildSpec, PagesSpec } from "./processes";
import { isOurHarness, parsePidFile, pidFileText, type PidRecord } from "./strays";

const STOP_GRACE_MS = 10_000;
const GONE_POLL_MS = 200;
const PS = "/bin/ps";
const PS_FOUND_NO_PROCESS = 1;
const NO_SUCH_FILE = "ENOENT";
const NO_SUCH_PROCESS = "ESRCH";

const execFileAsync = promisify(execFile);

export interface Child {
  readonly exited: Promise<void>;
  readonly stop: () => Promise<void>;
}

/** Starts the harness and records its pid; stopping it ends its whole process group, then forgets the pid. */
export function startHarness(spec: ChildSpec, logPath: string, pidFile: string): Child {
  const child = spawnGroupLeader(spec, logPath);
  const exited = new Promise<void>((resolve) => {
    child.once("exit", () => resolve());
    child.once("error", (error) => {
      appendFileSync(logPath, `${error.message}\n`);
      resolve();
    });
  });
  if (child.pid !== undefined) writeFileSync(pidFile, pidFileText(child.pid));
  const stop = async (): Promise<void> => {
    if (child.pid === undefined) return;
    await stopGroup(child.pid, exited);
    forgetHarnessPid(pidFile);
  };
  return { exited, stop };
}

/** Spawns the command as the leader of a new process group, its output appended to the log. */
function spawnGroupLeader(spec: ChildSpec, logPath: string): ChildProcess {
  const log = openSync(logPath, "a");
  const child = spawn(spec.command, [...spec.args], {
    cwd: spec.cwd,
    env: spec.env,
    detached: true,
    stdio: ["ignore", log, log],
  });
  closeSync(log);
  return child;
}

/** The page server runs on Electron's own Node, its output appended to the log. */
export function startPages(spec: PagesSpec, logPath: string): Child {
  const child = utilityProcess.fork(spec.modulePath, [], { cwd: spec.cwd, env: spec.env, stdio: "pipe" });
  const log = createWriteStream(logPath, { flags: "a" });
  child.stdout?.pipe(log, { end: false });
  child.stderr?.pipe(log, { end: false });
  const exited = new Promise<void>((resolve) => child.once("exit", () => resolve()));
  const stop = async (): Promise<void> => {
    child.kill();
    await graceForExit(exited);
  };
  return { exited, stop };
}

/** Stops the harness a run that died without quitting left behind, when its recorded pid still runs it; then forgets the pid. */
export async function stopStrayHarness(pidFile: string): Promise<void> {
  const record = readPidRecord(pidFile);
  if (record !== null && isOurHarness(await liveCommand(record.harnessPid))) {
    await stopStrayGroup(record.harnessPid);
  }
  forgetHarnessPid(pidFile);
}

function forgetHarnessPid(pidFile: string): void {
  rmSync(pidFile, { force: true });
}

function readPidRecord(pidFile: string): PidRecord | null {
  try {
    return parsePidFile(readFileSync(pidFile, "utf8"));
  } catch (error) {
    if (hasCode(error, NO_SUCH_FILE)) return null;
    throw error;
  }
}

/** The command line the pid runs, or null when no process has that pid. */
async function liveCommand(pid: number): Promise<string | null> {
  try {
    const { stdout } = await execFileAsync(PS, ["-o", "command=", "-p", String(pid)]);
    return stdout.trim();
  } catch (error) {
    if (hasCode(error, PS_FOUND_NO_PROCESS)) return null;
    throw error;
  }
}

async function stopGroup(leaderPid: number, leaderGone: Promise<void>): Promise<void> {
  signalGroup(leaderPid, "SIGTERM");
  await graceForExit(leaderGone);
  signalGroup(leaderPid, "SIGKILL");
}

async function stopStrayGroup(leaderPid: number): Promise<void> {
  const graceOver = new AbortController();
  await stopGroup(leaderPid, untilGone(leaderPid, graceOver.signal)).finally(() => graceOver.abort());
}

async function untilGone(pid: number, stopWaiting: AbortSignal): Promise<void> {
  while (!stopWaiting.aborted && isAlive(pid)) await delay(GONE_POLL_MS);
}

function isAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    if (hasCode(error, NO_SUCH_PROCESS)) return false;
    throw error;
  }
}

/** Signals every process in the group; a group already gone is not an error. */
function signalGroup(leaderPid: number, signal: NodeJS.Signals): void {
  try {
    process.kill(-leaderPid, signal);
  } catch (error) {
    if (!hasCode(error, NO_SUCH_PROCESS)) throw error;
  }
}

function hasCode(error: unknown, code: string | number): boolean {
  return error instanceof Error && "code" in error && error.code === code;
}

async function graceForExit(exited: Promise<void>): Promise<void> {
  const grace = new AbortController();
  const outcomes = [exited, delay(STOP_GRACE_MS, undefined, { signal: grace.signal })];
  await Promise.race(outcomes).finally(() => grace.abort());
}

import { spawn, type ChildProcess } from "node:child_process";
import { appendFileSync, closeSync, createWriteStream, openSync } from "node:fs";
import { setTimeout as delay } from "node:timers/promises";

import { utilityProcess } from "electron";

import type { ChildSpec, PagesSpec } from "./processes";

const STOP_GRACE_MS = 10_000;

export interface Child {
  readonly exited: Promise<void>;
  readonly stop: () => Promise<void>;
}

/** Starts the harness; stopping it ends its whole process group. */
export function startHarness(spec: ChildSpec, logPath: string): Child {
  const child = spawnGroupLeader(spec, logPath);
  const exited = new Promise<void>((resolve) => {
    child.once("exit", () => resolve());
    child.once("error", (error) => {
      appendFileSync(logPath, `${error.message}\n`);
      resolve();
    });
  });
  const stop = async (): Promise<void> => {
    if (child.pid === undefined) return;
    signalGroup(child.pid, "SIGTERM");
    await graceForExit(exited);
    signalGroup(child.pid, "SIGKILL");
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

/** Signals every process in the group; a group already gone is not an error. */
function signalGroup(leaderPid: number, signal: NodeJS.Signals): void {
  try {
    process.kill(-leaderPid, signal);
  } catch (error) {
    if (!isNoSuchProcess(error)) throw error;
  }
}

function isNoSuchProcess(error: unknown): boolean {
  return error instanceof Error && "code" in error && error.code === "ESRCH";
}

async function graceForExit(exited: Promise<void>): Promise<void> {
  const grace = new AbortController();
  const outcomes = [exited, delay(STOP_GRACE_MS, undefined, { signal: grace.signal })];
  await Promise.race(outcomes).finally(() => grace.abort());
}
